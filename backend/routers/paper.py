"""Phase 3C: paper trading management endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from services.price_feed import get_current_prices

router = APIRouter()


def _calc_unrealized(trade: models.Trade, prices: dict) -> float:
    price_data = prices.get(trade.symbol)
    if not price_data:
        return 0.0
    current = price_data["price"]
    if trade.side == "long":
        return (current - trade.entry_price) / trade.entry_price * trade.quantity
    else:
        return (trade.entry_price - current) / trade.entry_price * trade.quantity


@router.get("/stats")
def paper_stats(db: Session = Depends(get_db)):
    analysts = db.query(models.Analyst).all()
    all_trades = db.query(models.Trade).all()
    closed = [t for t in all_trades if t.status == "closed"]
    open_t = [t for t in all_trades if t.status == "open"]

    prices = get_current_prices()
    unrealized_pnl = sum(_calc_unrealized(t, prices) for t in open_t)

    total_initial = sum(a.initial_capital for a in analysts)
    total_current = sum(a.current_balance for a in analysts)
    locked_margin = sum(t.quantity / t.leverage for t in open_t if t.leverage)
    total_equity = total_current + locked_margin  # available cash + locked margin
    realized_pnl = sum(t.realized_pnl for t in closed)
    wins = [t for t in closed if t.realized_pnl > 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0.0
    total_return_pct = (
        (total_equity + unrealized_pnl - total_initial) / total_initial * 100
        if total_initial > 0
        else 0.0
    )

    gross_profit = sum(t.realized_pnl for t in closed if t.realized_pnl > 0)
    gross_loss = abs(sum(t.realized_pnl for t in closed if t.realized_pnl < 0))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 9.99

    return {
        "total_equity": round(total_equity, 2),
        "total_initial": round(total_initial, 2),
        "total_return_pct": round(total_return_pct, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "open_positions": len(open_t),
        "total_trades": len(closed),
        "win_rate": round(win_rate, 1),
        "profit_factor": pf,
    }


@router.get("/positions")
def open_positions(db: Session = Depends(get_db)):
    open_trades = db.query(models.Trade).filter(models.Trade.status == "open").all()
    analyst_map = {a.id: a for a in db.query(models.Analyst).all()}
    prices = get_current_prices()
    result = []
    for t in open_trades:
        a = analyst_map.get(t.analyst_id)
        upnl = _calc_unrealized(t, prices)
        current_price = prices.get(t.symbol, {}).get("price")
        result.append(
            {
                "id": t.id,
                "analyst": a.name if a else "?",
                "strategy": a.strategy if a else "?",
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "current_price": round(current_price, 4) if current_price else None,
                "quantity": t.quantity,
                "leverage": t.leverage,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "unrealized_pnl": round(upnl, 2),
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "notes": t.notes,
            }
        )
    return sorted(result, key=lambda x: x["entry_time"] or "", reverse=True)


@router.get("/trades")
def recent_trades(limit: int = 50, db: Session = Depends(get_db)):
    trades = (
        db.query(models.Trade)
        .filter(models.Trade.status == "closed")
        .order_by(models.Trade.exit_time.desc())
        .limit(limit)
        .all()
    )
    analyst_map = {a.id: a for a in db.query(models.Analyst).all()}
    result = []
    for t in trades:
        a = analyst_map.get(t.analyst_id)
        result.append(
            {
                "id": t.id,
                "analyst": a.name if a else "?",
                "strategy": a.strategy if a else "?",
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "leverage": t.leverage,
                "realized_pnl": t.realized_pnl,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            }
        )
    return result


@router.post("/reset")
def reset_paper_accounts(db: Session = Depends(get_db)):
    open_trades = db.query(models.Trade).filter(models.Trade.status == "open").all()
    for t in open_trades:
        t.status = "cancelled"
        t.exit_time = datetime.utcnow()

    analysts = db.query(models.Analyst).all()
    for a in analysts:
        a.current_balance = a.initial_capital
        a.consecutive_losses = 0
        a.paused_until = None
        a.pause_reason = None
        a.peak_balance = a.initial_capital

    db.query(models.BalanceSnapshot).delete()

    risk_state = db.query(models.RiskState).first()
    if risk_state:
        total = sum(a.initial_capital for a in analysts)
        risk_state.portfolio_peak = total

    db.commit()
    return {"ok": True, "reset": len(analysts)}
