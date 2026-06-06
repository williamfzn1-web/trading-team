"""
Walk-forward backtesting engine v2.

Key improvements over v1:
  - EMA200 trend filter: only trade WITH the macro trend (biggest win-rate fix)
  - Multi-position: up to strategy.max_positions concurrent trades
  - Realistic entry: next bar's open instead of signal bar's close
  - Commission: 0.075% per side (Binance taker)
  - Pre-computed trend array: O(n) not O(n*lookback)
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

WARMUP_BARS = 210  # bars skipped for indicator warm-up
LOOKBACK = 300  # bars passed to strategy.get_signal() (bounds cost to O(n))
INITIAL_CAPITAL = 10_000.0
COMMISSION = 0.00075  # 0.075 % per side (Binance VIP0 taker)
USE_TREND_FILTER = True  # EMA200 alignment gate
TREND_PERIOD = 200
COOLDOWN_BARS = 24  # min bars between same-direction entries (= 24 h on 1h chart)


@dataclass
class BTTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    leverage: int
    pnl: float  # net of commission
    entry_dt: str  # ISO 8601
    exit_dt: str
    exit_reason: str  # 'stop_loss' | 'take_profit' | 'end_of_data'


# ── Internal helpers ──────────────────────────────────────────────────────


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _precompute_ema(candles: list, period: int) -> list:
    """Returns a list of EMA values (None for first period-1 bars)."""
    result: list = [None] * len(candles)
    if len(candles) < period:
        return result
    alpha = 2.0 / (period + 1)
    # Seed with SMA of first `period` closes
    val = sum(c[4] for c in candles[:period]) / period
    result[period - 1] = val
    for i in range(period, len(candles)):
        val = candles[i][4] * alpha + val * (1 - alpha)
        result[i] = val
    return result


def _close_position(
    pos: dict,
    exit_price: float,
    exit_dt: str,
    exit_reason: str,
    balance: float,
    peak: float,
    trades: list,
    equity_curve: list,
) -> tuple:
    """Close a position, return updated (balance, peak)."""
    ep, qty, lev = pos["ep"], pos["qty"], pos["lev"]
    if pos["side"] == "long":
        pnl = (exit_price - ep) / ep * qty
    else:
        pnl = (ep - exit_price) / ep * qty
    pnl -= qty * COMMISSION  # exit-side commission
    margin = qty / lev
    balance += margin + pnl
    peak = max(peak, balance)
    trades.append(
        BTTrade(
            symbol=pos["symbol"],
            side=pos["side"],
            entry_price=ep,
            exit_price=round(exit_price, 6),
            quantity=qty,
            leverage=lev,
            pnl=round(pnl, 2),
            entry_dt=pos["entry_dt"],
            exit_dt=exit_dt,
            exit_reason=exit_reason,
        )
    )
    equity_curve.append([exit_dt, round(balance, 2)])
    return balance, peak


# ── Public API ────────────────────────────────────────────────────────────


def _backtest_bitget_filter(strategy_name: str, action: str, ctx: dict) -> bool:
    """Returns False if Bitget data blocks this trade (mirrors live _bitget_filter)."""
    rate = ctx.get("funding_rate", 0.0)
    long_pct = ctx.get("long_pct", 50.0)

    if strategy_name == "Arbitrage":
        if rate > 0.08 and action == "long": return False
        if rate < -0.04 and action == "short": return False
    elif strategy_name == "Macro/Sentiment":
        if long_pct > 68 and action == "long": return False
        if long_pct < 32 and action == "short": return False
    elif strategy_name == "Capital Flow":
        if rate > 0.02 and action == "short": return False
        if rate < -0.02 and action == "long": return False
    elif strategy_name == "Whale Hunting":
        if rate > 0.10 and action == "long": return False
        if rate < -0.05 and action == "short": return False
    elif strategy_name == "On-chain Data":
        if rate > 0.06 and action == "long": return False
        if rate < -0.03 and action == "short": return False
    elif strategy_name == "SMC":
        if rate > 0.07 and action == "long": return False
        if rate < -0.04 and action == "short": return False
    elif strategy_name == "Liquidity":
        if action == "long" and long_pct < 40: return False
        if action == "short" and long_pct > 60: return False
    elif strategy_name == "Wyckoff Spring":
        if action == "long" and long_pct < 38: return False
        if action == "short" and long_pct > 62: return False
    elif strategy_name == "Order Flow":
        if action == "long" and rate < -0.03: return False
        if action == "short" and rate > 0.05: return False
    elif strategy_name == "Mean Reversion":
        if action == "long" and rate < -0.05: return False
        if action == "short" and rate > 0.04: return False
    elif strategy_name == "Auction Theory":
        if action == "long" and rate < -0.04: return False
        if action == "short" and rate > 0.06: return False
        if long_pct > 65 and action == "long": return False
    elif strategy_name == "SuperTrend":
        if action == "long" and rate < -0.04: return False
        if action == "long" and long_pct > 65: return False
        if action == "short" and rate > 0.07: return False
    elif strategy_name == "Order Book Imbalance":
        if action == "long" and rate < -0.03: return False
        if action == "long" and long_pct < 35: return False
        if action == "short" and rate > 0.06: return False
    elif strategy_name == "ICT Fair Value Gap":
        if action == "long" and rate > 0.07: return False
        if action == "long" and long_pct > 68: return False
        if action == "short" and rate < -0.03: return False
    return True


def simulate(
    strategy,
    ohlcv_map: dict,
    use_trend_filter: bool = USE_TREND_FILTER,
    bitget_history: dict | None = None,
    strategy_name: str = "",
) -> tuple[list[BTTrade], dict, list]:
    """
    Walk-forward simulation.
    Returns (trades, metrics_dict, equity_curve).
    equity_curve: [[iso_timestamp, balance], ...]
    """
    primary = strategy.symbols[0]
    candles = ohlcv_map.get(primary, [])
    n = len(candles)

    if n < WARMUP_BARS + 50:
        return [], {}, []

    # Pre-compute EMA200 for O(n) trend filter
    ema200 = _precompute_ema(candles, TREND_PERIOD) if use_trend_filter else [None] * n

    balance = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    open_positions: list[dict] = []
    trades: list[BTTrade] = []
    equity_curve: list = [[_iso(candles[WARMUP_BARS][0]), round(balance, 2)]]
    last_entry_bar: dict[str, int] = {}   # side -> bar index of last entry

    for i in range(WARMUP_BARS, n - 1):
        bar = candles[i]
        next_bar = candles[i + 1]
        b_high, b_low = bar[2], bar[3]
        bar_dt = _iso(bar[0])

        # ── 1. Check exits for all open positions ─────────────────────
        still_open = []
        for pos in open_positions:
            exit_price = exit_reason = None
            if pos["side"] == "long":
                if b_low <= pos["sl"]:
                    exit_price, exit_reason = pos["sl"], "stop_loss"
                elif b_high >= pos["tp"]:
                    exit_price, exit_reason = pos["tp"], "take_profit"
            else:
                if b_high >= pos["sl"]:
                    exit_price, exit_reason = pos["sl"], "stop_loss"
                elif b_low <= pos["tp"]:
                    exit_price, exit_reason = pos["tp"], "take_profit"

            if exit_price is not None:
                balance, peak = _close_position(
                    pos,
                    exit_price,
                    bar_dt,
                    exit_reason,
                    balance,
                    peak,
                    trades,
                    equity_curve,
                )
            else:
                still_open.append(pos)
        open_positions = still_open

        # ── 2. Check if we can open a new position ────────────────────
        if len(open_positions) >= strategy.max_positions or balance < 500:
            continue

        # Build lookback slice for signal (bounded window → O(n))
        start = max(0, i - LOOKBACK + 1)
        sliced = {
            sym: ohlcv_map[sym][start : i + 1]
            for sym in strategy.symbols
            if sym in ohlcv_map
        }
        try:
            signal = strategy.get_signal(sliced)
        except Exception as exc:
            if not getattr(simulate, "_logged", None):
                simulate._logged = set()
            key = f"{strategy.name}:{type(exc).__name__}"
            if key not in simulate._logged:
                simulate._logged.add(key)
                print(f"[backtest] {strategy.name} exception: {exc}")
            continue

        if signal.action not in ("long", "short"):
            continue

        # Bitget historical filter — mirrors live _bitget_filter
        if bitget_history and strategy_name:
            from services.bitget_history import lookup_bitget_ctx
            ctx = lookup_bitget_ctx(bar[0], bitget_history)
            if ctx and not _backtest_bitget_filter(strategy_name, signal.action, ctx):
                continue

        # No duplicate direction already open
        if signal.action in {p["side"] for p in open_positions}:
            continue

        # Cooldown: prevent same-direction re-entry within COOLDOWN_BARS bars
        if i - last_entry_bar.get(signal.action, -(COOLDOWN_BARS + 1)) < COOLDOWN_BARS:
            continue

        # ── Trend filter: only trade WITH EMA200 direction ────────────
        # Strategies with bypass_trend_filter=True skip this gate (e.g. On-chain)
        strategy_bypasses = getattr(strategy, "bypass_trend_filter", False)
        if use_trend_filter and not strategy_bypasses and ema200[i] is not None:
            b_close = bar[4]
            if signal.action == "long" and b_close < ema200[i]:
                continue  # don't buy below EMA200 (downtrend)
            if signal.action == "short" and b_close > ema200[i]:
                continue  # don't short above EMA200 (uptrend)

        # ── Enter at next bar's OPEN (realistic fill) ─────────────────
        entry_price = next_bar[1]
        qty = round(balance * strategy.risk_pct, 2)
        margin = qty / strategy.leverage
        if margin > balance * 0.45 or qty <= 0:
            continue

        balance -= margin + qty * COMMISSION  # entry commission
        equity_curve.append([_iso(next_bar[0]), round(balance, 2)])  # capture margin lock

        if signal.action == "long":
            sl = entry_price * (1 - signal.stop_loss_pct)
            tp = entry_price * (1 + signal.take_profit_pct)
        else:
            sl = entry_price * (1 + signal.stop_loss_pct)
            tp = entry_price * (1 - signal.take_profit_pct)

        open_positions.append(
            {
                "symbol": primary,
                "side": signal.action,
                "ep": entry_price,
                "qty": qty,
                "lev": strategy.leverage,
                "sl": sl,
                "tp": tp,
                "entry_dt": _iso(next_bar[0]),
            }
        )
        last_entry_bar[signal.action] = i

    # ── Force-close remaining positions at last bar's close ───────────
    last = candles[-1]
    last_price, last_dt = last[4], _iso(last[0])
    for pos in open_positions:
        balance, peak = _close_position(
            pos,
            last_price,
            last_dt,
            "end_of_data",
            balance,
            peak,
            trades,
            equity_curve,
        )

    metrics = _calc_metrics(trades, INITIAL_CAPITAL, balance)

    # Override max_drawdown with value computed from full equity curve
    # (includes margin-lock dips at open time, which trade-list replay misses)
    eq_peak = INITIAL_CAPITAL
    real_max_dd = 0.0
    for _, eq_bal in equity_curve:
        if eq_bal > eq_peak:
            eq_peak = eq_bal
        dd = (eq_peak - eq_bal) / eq_peak * 100
        if dd > real_max_dd:
            real_max_dd = dd
    metrics["max_drawdown_pct"] = round(real_max_dd, 2)

    return trades, metrics, equity_curve


def _calc_metrics(trades: list[BTTrade], initial: float, final: float) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "total_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "avg_win_usdt": 0.0,
            "avg_loss_usdt": 0.0,
            "final_capital": round(initial, 2),
        }

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    # Max drawdown from running equity
    bal = initial
    peak = initial
    max_dd = 0.0
    for t in trades:
        bal += t.pnl
        if bal > peak:
            peak = bal
        dd = (peak - bal) / peak * 100
        if dd > max_dd:
            max_dd = dd

    total_return = (final - initial) / initial * 100
    win_rate = len(wins) / len(trades) * 100
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 9.99
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0

    # Sharpe: annualized via trade frequency
    returns = np.array([t.pnl / initial for t in trades])
    sharpe = 0.0
    if len(returns) > 1 and returns.std() > 0:
        try:
            n_days = max(
                1,
                (
                    datetime.fromisoformat(trades[-1].exit_dt)
                    - datetime.fromisoformat(trades[0].entry_dt)
                ).days,
            )
            trades_per_year = len(trades) / n_days * 365
            sharpe = float(returns.mean() / returns.std() * np.sqrt(trades_per_year))
        except Exception:
            pass

    # Annualized return: compound from actual date range, fallback to 180-day assumption
    try:
        n_days = max(
            1,
            (
                datetime.fromisoformat(trades[-1].exit_dt)
                - datetime.fromisoformat(trades[0].entry_dt)
            ).days,
        )
    except Exception:
        n_days = 180
    annualized = ((final / initial) ** (365.0 / n_days) - 1) * 100

    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(annualized, 1),
        "sharpe_ratio": round(float(np.clip(sharpe, -10, 20)), 3),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(min(profit_factor, 9.99), 2),
        "avg_win_usdt": round(avg_win, 2),
        "avg_loss_usdt": round(avg_loss, 2),
        "final_capital": round(final, 2),
    }
