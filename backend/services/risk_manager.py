"""
Risk management layer.

Rules:
  1. Portfolio circuit breaker  — halt all new trades if drawdown > 15% from peak
  2. Daily loss limit           — pause analyst until midnight if day loss > 5%
  3. Concentration limit        — max 4 analysts same symbol + same side open
  4. Consecutive loss reduction — 3 losses in a row  -> position size halved
  5. Consecutive loss pause     — 5 losses in a row  -> paused 24 h
  6. Minimum balance            — won't open if balance < $500
"""

from datetime import datetime, timedelta

import models

# --- Parameters ---
DAILY_LOSS_LIMIT_PCT = 0.05  # 5 %
PORTFOLIO_DRAWDOWN_LIMIT = 0.40  # 40% — nuclear last resort only
MAX_SAME_DIRECTION = 4  # analysts
CONSEC_REDUCE_AT = 3  # losses before 50 % size
CONSEC_PAUSE_AT = 5  # losses before 24 h pause
MIN_BALANCE = 500.0


# ---------- internal helpers ----------


def _analyst_equity(analyst, db) -> float:
    """Real equity = free balance + margin locked in open trades."""
    open_trades = (
        db.query(models.Trade)
        .filter(models.Trade.analyst_id == analyst.id, models.Trade.status == "open")
        .all()
    )
    locked = sum(t.quantity / t.leverage for t in open_trades)
    return analyst.current_balance + locked


def _risk_state(db) -> models.RiskState:
    state = db.query(models.RiskState).first()
    if not state:
        state = models.RiskState(portfolio_peak=0.0)
        db.add(state)
        db.flush()
    return state


# ---------- public functions ----------


def update_portfolio_peak(db, analysts: list):
    """Update all-time portfolio + per-analyst peaks. Call at start of each tick."""
    total = sum(_analyst_equity(a, db) for a in analysts)
    state = _risk_state(db)
    if total > state.portfolio_peak:
        state.portfolio_peak = round(total, 2)
        state.updated_at = datetime.utcnow()
    for a in analysts:
        equity = _analyst_equity(a, db)
        if a.peak_balance is None or equity > a.peak_balance:
            a.peak_balance = round(equity, 2)
    return total, state.portfolio_peak


def check_portfolio_circuit_breaker(db) -> tuple[bool, str]:
    """(can_trade, reason). Blocks all new trades when portfolio drawdown >= limit."""
    state = _risk_state(db)
    if state.portfolio_peak == 0:
        return True, ""
    analysts = db.query(models.Analyst).all()
    total = sum(_analyst_equity(a, db) for a in analysts)
    dd = (state.portfolio_peak - total) / state.portfolio_peak
    if dd >= PORTFOLIO_DRAWDOWN_LIMIT:
        return (
            False,
            f"Portfolio drawdown {dd*100:.1f}% >= {PORTFOLIO_DRAWDOWN_LIMIT*100:.0f}% limit",
        )
    return True, ""


def check_analyst_can_trade(db, analyst) -> tuple[bool, str]:
    """(can_trade, reason). Checks pause expiry, balance, and daily loss."""
    now = datetime.utcnow()

    # Manual force-enable overrides all pause checks until expiry
    if analyst.force_trade_until and analyst.force_trade_until > now:
        if analyst.current_balance < MIN_BALANCE:
            return False, f"Balance below ${MIN_BALANCE:.0f}"
        return True, ""

    # Active pause
    if analyst.paused_until and analyst.paused_until > now:
        hours_left = int((analyst.paused_until - now).total_seconds() / 3600)
        return False, f"{analyst.pause_reason} | {hours_left}h left"

    # Balance floor
    if analyst.current_balance < MIN_BALANCE:
        return False, f"Balance below ${MIN_BALANCE:.0f}"

    # Daily loss limit
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_closed = (
        db.query(models.Trade)
        .filter(
            models.Trade.analyst_id == analyst.id,
            models.Trade.status == "closed",
            models.Trade.exit_time >= today_start,
        )
        .all()
    )
    today_pnl = sum(t.realized_pnl for t in today_closed)
    day_start_balance = analyst.current_balance - today_pnl

    if day_start_balance > 0 and today_pnl < -(
        day_start_balance * DAILY_LOSS_LIMIT_PCT
    ):
        midnight = now.replace(hour=23, minute=59, second=59)
        analyst.paused_until = midnight
        analyst.pause_reason = f"Daily loss -{DAILY_LOSS_LIMIT_PCT*100:.0f}%"
        print(f"  [RISK] {analyst.name} daily loss limit hit, paused until midnight")
        return (
            False,
            f"Daily loss ${today_pnl:.0f} exceeded -{DAILY_LOSS_LIMIT_PCT*100:.0f}% limit",
        )

    return True, ""


def check_concentration(db, symbol: str, side: str) -> tuple[bool, str]:
    """(can_add, reason). Prevents piling into the same direction on one symbol."""
    count = (
        db.query(models.Trade)
        .filter(
            models.Trade.symbol == symbol,
            models.Trade.side == side,
            models.Trade.status == "open",
        )
        .count()
    )
    if count >= MAX_SAME_DIRECTION:
        return (
            False,
            f"Concentration: {count}/{MAX_SAME_DIRECTION} analysts {side} {symbol}",
        )
    return True, ""


def get_size_multiplier(analyst) -> float:
    """Returns 0.5 when on a loss streak, 1.0 otherwise."""
    return 0.5 if (analyst.consecutive_losses or 0) >= CONSEC_REDUCE_AT else 1.0


def update_after_close(db, trade, analyst):
    """Update risk state after every trade close."""
    if trade.realized_pnl < 0:
        analyst.consecutive_losses = (analyst.consecutive_losses or 0) + 1
        if analyst.consecutive_losses >= CONSEC_PAUSE_AT:
            analyst.paused_until = datetime.utcnow() + timedelta(hours=24)
            analyst.pause_reason = f"{CONSEC_PAUSE_AT} consecutive losses"
            print(
                f"  [RISK] {analyst.name} paused 24h: {CONSEC_PAUSE_AT} consecutive losses"
            )
        elif analyst.consecutive_losses == CONSEC_REDUCE_AT:
            print(
                f"  [RISK] {analyst.name} size halved: {CONSEC_REDUCE_AT} consecutive losses"
            )
    else:
        if (analyst.consecutive_losses or 0) > 0:
            print(
                f"  [RISK] {analyst.name} streak reset (was {analyst.consecutive_losses}L)"
            )
        analyst.consecutive_losses = 0

    if analyst.peak_balance is None or analyst.current_balance > analyst.peak_balance:
        analyst.peak_balance = analyst.current_balance


def get_risk_status(db) -> dict:
    """Full risk snapshot for the REST endpoint."""
    now = datetime.utcnow()
    state = _risk_state(db)
    analysts = db.query(models.Analyst).all()
    total = sum(_analyst_equity(a, db) for a in analysts)
    peak = state.portfolio_peak or total
    portfolio_dd = (peak - total) / peak if peak > 0 else 0.0
    portfolio_ok, portfolio_msg = check_portfolio_circuit_breaker(db)

    analyst_rows = []
    for a in analysts:
        can_trade, reason = check_analyst_can_trade(db, a)
        a_peak = a.peak_balance or a.initial_capital
        a_equity = _analyst_equity(a, db)
        a_dd = (a_peak - a_equity) / a_peak if a_peak > 0 else 0.0
        analyst_rows.append(
            {
                "id": a.id,
                "name": a.name,
                "strategy": a.strategy,
                "avatar_color": a.avatar_color,
                "can_trade": can_trade,
                "pause_reason": reason if not can_trade else None,
                "paused_until": (
                    a.paused_until.isoformat()
                    if a.paused_until and a.paused_until > now
                    else None
                ),
                "consecutive_losses": a.consecutive_losses or 0,
                "size_multiplier": get_size_multiplier(a),
                "peak_balance": round(a_peak, 2),
                "current_balance": round(a.current_balance, 2),
                "drawdown_pct": round(a_dd * 100, 2),
            }
        )

    return {
        "portfolio": {
            "total_balance": round(total, 2),
            "peak_balance": round(peak, 2),
            "drawdown_pct": round(portfolio_dd * 100, 2),
            "circuit_breaker_active": not portfolio_ok,
            "circuit_breaker_msg": portfolio_msg if not portfolio_ok else None,
            "drawdown_limit_pct": PORTFOLIO_DRAWDOWN_LIMIT * 100,
        },
        "analysts": analyst_rows,
        "rules": {
            "daily_loss_limit_pct": DAILY_LOSS_LIMIT_PCT * 100,
            "portfolio_drawdown_limit_pct": PORTFOLIO_DRAWDOWN_LIMIT * 100,
            "max_same_direction": MAX_SAME_DIRECTION,
            "consec_reduce_at": CONSEC_REDUCE_AT,
            "consec_pause_at": CONSEC_PAUSE_AT,
            "min_balance": MIN_BALANCE,
        },
    }
