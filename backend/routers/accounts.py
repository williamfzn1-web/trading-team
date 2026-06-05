from collections import defaultdict

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from services.portfolio import get_account_metrics
from services.price_feed import get_current_prices

router = APIRouter()


def _build_metrics(analyst, db: Session, current_prices: dict) -> dict:
    trades = db.query(models.Trade).filter(models.Trade.analyst_id == analyst.id).all()
    history = (
        db.query(models.BalanceSnapshot)
        .filter(models.BalanceSnapshot.analyst_id == analyst.id)
        .all()
    )
    return get_account_metrics(analyst, trades, history, current_prices)


@router.get("/")
def list_accounts(db: Session = Depends(get_db)):
    prices = get_current_prices()
    return [_build_metrics(a, db, prices) for a in db.query(models.Analyst).all()]


@router.get("/positions/open")
def open_positions(db: Session = Depends(get_db)):
    trades = db.query(models.Trade).filter(models.Trade.status == "open").all()
    prices = get_current_prices() or {}
    analysts_map = {a.id: a for a in db.query(models.Analyst).all()}
    result = []
    for t in trades:
        analyst = analysts_map.get(t.analyst_id)
        base = t.symbol.split("/")[0]
        price_key = f"{base}/USDT"
        current_price = prices.get(price_key, {}).get("price", 0) if prices else 0
        if current_price and t.entry_price:
            if t.side == "long":
                unrealized = (current_price - t.entry_price) / t.entry_price * t.quantity
            else:
                unrealized = (t.entry_price - current_price) / t.entry_price * t.quantity
        else:
            unrealized = 0.0
        lev = t.leverage if t.leverage and t.leverage > 0 else 1
        result.append({
            "id": t.id,
            "analyst_id": t.analyst_id,
            "analyst_name": analyst.name if analyst else "?",
            "analyst_color": analyst.avatar_color if analyst else "#666",
            "strategy": analyst.strategy if analyst else "?",
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry_price,
            "current_price": round(current_price, 2),
            "quantity": t.quantity,
            "leverage": lev,
            "margin": round(t.quantity / lev, 2),
            "unrealized_pnl": round(unrealized, 2),
            "stop_loss": t.stop_loss,
            "take_profit": t.take_profit,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
        })
    result.sort(key=lambda x: x["unrealized_pnl"])
    return result


@router.get("/daily-pnl")
def daily_pnl(db: Session = Depends(get_db)):
    """Daily realized P&L grouped by trade exit date."""
    trades = (
        db.query(models.Trade)
        .filter(models.Trade.status == "closed", models.Trade.exit_time.isnot(None))
        .all()
    )
    daily: dict = defaultdict(float)
    for t in trades:
        day = t.exit_time.strftime("%Y-%m-%d")
        daily[day] += t.realized_pnl
    return [
        {"date": day, "pnl": round(pnl, 2)}
        for day, pnl in sorted(daily.items())
    ]


@router.get("/correlation")
def correlation_matrix(db: Session = Depends(get_db)):
    analysts = db.query(models.Analyst).all()
    if len(analysts) < 2:
        return {"analysts": [], "matrix": []}
    snapshots = (
        db.query(models.BalanceSnapshot)
        .order_by(models.BalanceSnapshot.timestamp)
        .all()
    )
    analyst_series: dict = defaultdict(dict)
    for s in snapshots:
        day = s.timestamp.strftime("%Y-%m-%d")
        analyst_series[s.analyst_id][day] = s.balance
    all_days = sorted({s.timestamp.strftime("%Y-%m-%d") for s in snapshots})
    if len(all_days) < 5:
        return {"analysts": [], "matrix": []}
    returns_map = {}
    for a in analysts:
        series = analyst_series.get(a.id, {})
        last = a.initial_capital
        balances = []
        for day in all_days:
            b = series.get(day, last)
            balances.append(b)
            last = b
        arr = np.array(balances, dtype=float)
        denom = np.where(arr[:-1] != 0, arr[:-1], 1)
        returns_map[a.id] = np.diff(arr) / denom
    matrix = []
    for a in analysts:
        row = []
        for b in analysts:
            ra = returns_map.get(a.id, np.array([]))
            rb = returns_map.get(b.id, np.array([]))
            if len(ra) < 2 or len(rb) < 2 or np.std(ra) == 0 or np.std(rb) == 0:
                row.append(1.0 if a.id == b.id else 0.0)
            else:
                row.append(round(float(np.corrcoef(ra, rb)[0, 1]), 3))
        matrix.append(row)
    return {
        "analysts": [
            {"id": a.id, "name": a.name, "strategy": a.strategy, "color": a.avatar_color}
            for a in analysts
        ],
        "matrix": matrix,
    }


@router.get("/combined-equity")
def combined_equity(db: Session = Depends(get_db)):
    """Portfolio equity curve: initial capital + cumulative realized PnL per day."""
    analysts = db.query(models.Analyst).all()
    if not analysts:
        return []

    total_initial = sum(a.initial_capital for a in analysts)

    trades = (
        db.query(models.Trade)
        .filter(models.Trade.status == "closed", models.Trade.exit_time.isnot(None))
        .order_by(models.Trade.exit_time)
        .all()
    )

    daily_pnl: dict = defaultdict(float)
    for t in trades:
        day = t.exit_time.strftime("%Y-%m-%d")
        daily_pnl[day] += t.realized_pnl

    # Find start date from earliest trade entry or fallback to snapshot
    earliest = None
    if trades:
        earliest_entry = min(
            t.entry_time for t in db.query(models.Trade).all() if t.entry_time
        )
        earliest = earliest_entry.strftime("%Y-%m-%d")

    # Starting point (one day before first trade, or just use a sentinel)
    result = []
    start_day = earliest or "2026-05-31"
    result.append({"timestamp": start_day, "balance": total_initial})

    cumulative = 0.0
    for day in sorted(daily_pnl):
        if day <= start_day:
            continue
        cumulative += daily_pnl[day]
        result.append({"timestamp": day, "balance": round(total_initial + cumulative, 2)})

    # Add today's point with locked margin included
    from datetime import date
    today_str = date.today().isoformat()
    if not result or result[-1]["timestamp"] != today_str:
        open_trades = db.query(models.Trade).filter(models.Trade.status == "open").all()
        locked_margin = sum(t.quantity / t.leverage for t in open_trades if t.leverage)
        current_balance = sum(a.current_balance for a in analysts)
        result.append({"timestamp": today_str, "balance": round(current_balance + locked_margin, 2)})

    return result


@router.get("/{analyst_id}")
def get_account(analyst_id: int, db: Session = Depends(get_db)):
    analyst = db.query(models.Analyst).filter(models.Analyst.id == analyst_id).first()
    if not analyst:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Analyst not found")
    return _build_metrics(analyst, db, get_current_prices())


@router.get("/{analyst_id}/equity-curve")
def analyst_equity_curve(analyst_id: int, db: Session = Depends(get_db)):
    snapshots = (
        db.query(models.BalanceSnapshot)
        .filter(models.BalanceSnapshot.analyst_id == analyst_id)
        .order_by(models.BalanceSnapshot.timestamp)
        .all()
    )
    return [
        {
            "timestamp": s.timestamp.isoformat(),
            "balance": s.balance,
            "unrealized_pnl": s.unrealized_pnl,
        }
        for s in snapshots
    ]


@router.get("/{analyst_id}/trades")
def analyst_trades(analyst_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Trade)
        .filter(models.Trade.analyst_id == analyst_id)
        .order_by(models.Trade.entry_time.desc())
        .all()
    )


@router.get("/{analyst_id}/messages")
def analyst_messages(analyst_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(models.GroupMessage)
        .filter(models.GroupMessage.analyst_id == analyst_id)
        .order_by(models.GroupMessage.timestamp.desc())
        .limit(limit)
        .all()
    )
