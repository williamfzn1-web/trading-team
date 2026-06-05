"""
Shadow broker: mirrors every live trade as a parallel paper trade.
When TRADING_MODE=live, call open_shadow() / close_shadow() alongside
the real exchange calls to get a 1:1 comparison of real vs simulated fills.
"""

from datetime import datetime
import models


def open_shadow(db, live_trade: models.Trade) -> models.Trade:
    """Create a shadow paper trade mirroring a live trade at the same price."""
    shadow = models.Trade(
        analyst_id=live_trade.analyst_id,
        symbol=live_trade.symbol,
        side=live_trade.side,
        entry_price=live_trade.entry_price,
        quantity=live_trade.quantity,
        leverage=live_trade.leverage,
        stop_loss=live_trade.stop_loss,
        take_profit=live_trade.take_profit,
        notes=f"[SHADOW] {live_trade.notes or ''}",
        status="open",
        entry_time=live_trade.entry_time,
        mode="shadow",
    )
    db.add(shadow)
    db.flush()  # get shadow.id before caller commits
    return shadow


def close_shadow(db, live_trade: models.Trade, exit_price: float):
    """Close the shadow trade that mirrors the given live trade."""
    shadow = (
        db.query(models.Trade)
        .filter(
            models.Trade.analyst_id == live_trade.analyst_id,
            models.Trade.symbol == live_trade.symbol,
            models.Trade.side == live_trade.side,
            models.Trade.mode == "shadow",
            models.Trade.status == "open",
            models.Trade.entry_time == live_trade.entry_time,
        )
        .first()
    )
    if not shadow:
        return None

    if shadow.side == "long":
        pnl = (exit_price - shadow.entry_price) / shadow.entry_price * shadow.quantity
    else:
        pnl = (shadow.entry_price - exit_price) / shadow.entry_price * shadow.quantity

    shadow.exit_price = round(exit_price, 4)
    shadow.realized_pnl = round(pnl, 2)
    shadow.status = "closed"
    shadow.exit_time = datetime.utcnow()
    return shadow
