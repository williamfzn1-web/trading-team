import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager  # strategy reload: r3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import models
from database import SessionLocal, engine
from migrate import migrate
from add_analysts import add_analysts
from routers import accounts, messages, prices, trades
from routers import risk as risk_router
from routers import backtest as backtest_router
from routers import paper as paper_router
from routers import shadow as shadow_router
from services.ai_analyst import run_discussion_round
from services.portfolio import get_account_metrics
from services.price_feed import (
    add_connection,
    get_current_prices,
    price_feed_loop,
    remove_connection,
)
from services.strategy_engine import strategy_engine_loop

migrate()  # add new columns to existing DB before create_all
models.Base.metadata.create_all(bind=engine)
add_analysts()  # add new analysts if not already present


async def _get_all_account_data(current_prices: dict) -> list:
    db = SessionLocal()
    try:
        analysts = db.query(models.Analyst).all()
        result = []
        for analyst in analysts:
            analyst_trades = (
                db.query(models.Trade)
                .filter(models.Trade.analyst_id == analyst.id)
                .all()
            )
            history = (
                db.query(models.BalanceSnapshot)
                .filter(models.BalanceSnapshot.analyst_id == analyst.id)
                .all()
            )
            result.append(
                get_account_metrics(analyst, analyst_trades, history, current_prices)
            )
        return result
    finally:
        db.close()


async def _discussion_loop():
    """AI group discussion: 3 analysts post every 20 minutes."""
    print("[discussion] Started - first round in 90s")
    await asyncio.sleep(90)
    while True:
        try:
            await run_discussion_round(SessionLocal, get_current_prices(), n_speakers=3)
        except Exception as e:
            print(f"[discussion] Error: {e}")
        await asyncio.sleep(1200)  # every 20 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(price_feed_loop(_get_all_account_data)),
        asyncio.create_task(strategy_engine_loop()),
        asyncio.create_task(_discussion_loop()),
    ]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Trading Platform API", version="2.0.0", lifespan=lifespan)

_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(risk_router.router, prefix="/api/risk", tags=["risk"])
app.include_router(backtest_router.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(paper_router.router, prefix="/api/paper", tags=["paper"])
app.include_router(shadow_router.router, prefix="/api/shadow", tags=["shadow"])


@app.get("/api/health")
def health():
    return {"status": "ok", "phase": 3}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    add_connection(websocket)
    try:
        current_prices = get_current_prices()
        account_data = await _get_all_account_data(current_prices)
        await websocket.send_text(
            json.dumps(
                {"type": "update", "prices": current_prices, "accounts": account_data}
            )
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        remove_connection(websocket)
