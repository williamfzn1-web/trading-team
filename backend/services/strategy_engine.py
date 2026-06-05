"""Strategy engine: orchestrates all 10 analysts every 5 minutes."""

import asyncio
from datetime import datetime

import models
import config
from database import SessionLocal
from services.market_data import get_ohlcv_multi
from services.price_feed import get_current_prices
from services.telegram_bot import notify_close, notify_open
from services.bitget_data import get_market_context

from services.risk_manager import (
    check_analyst_can_trade,
    check_concentration,
    check_portfolio_circuit_breaker,
    get_size_multiplier,
    update_after_close,
    update_portfolio_peak,
)
from strategies.smc import SMCStrategy
from strategies.auction_theory import AuctionTheoryStrategy
from strategies.order_flow import OrderFlowStrategy
from strategies.onchain import OnChainStrategy
from strategies.arbitrage import ArbitrageStrategy
from strategies.traditional_ta import TraditionalTAStrategy
from strategies.whale_hunting import WhaleHuntingStrategy
from strategies.capital_flow import CapitalFlowStrategy
from strategies.liquidity import LiquidityStrategy
from strategies.macro_sentiment import MacroSentimentStrategy
from strategies.momentum_breakout import MomentumBreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.volatility_breakout import VolatilityBreakoutStrategy
from strategies.adx_trend import ADXTrendStrategy
from strategies.order_book_imbalance import OrderBookImbalanceStrategy
from strategies.ict_fvg import ICTFairValueGapStrategy
from strategies.wyckoff_spring import WyckoffSpringStrategy
from strategies.vwap_reversion import VWAPReversionStrategy
from strategies.bb_squeeze import BollingerSqueezeStrategy
from strategies.supertrend_momentum import SuperTrendMomentumStrategy
from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.london_breakout import LondonBreakoutStrategy
from strategies.cross_momentum import CrossMomentumStrategy

STRATEGY_MAP = {
    "SMC": SMCStrategy(),
    "Auction Theory": AuctionTheoryStrategy(),
    "Order Flow": OrderFlowStrategy(),
    "On-chain Data": OnChainStrategy(),
    "Arbitrage": ArbitrageStrategy(),
    "Traditional TA": TraditionalTAStrategy(),
    "Whale Hunting": WhaleHuntingStrategy(),
    "Capital Flow": CapitalFlowStrategy(),
    "Liquidity": LiquidityStrategy(),
    "Macro/Sentiment": MacroSentimentStrategy(),
    "Momentum Breakout": MomentumBreakoutStrategy(),
    "Mean Reversion": MeanReversionStrategy(),
    "Volatility Breakout": VolatilityBreakoutStrategy(),
    "ADX Trend": ADXTrendStrategy(),
    "Order Book Imbalance": OrderBookImbalanceStrategy(),
    "ICT Fair Value Gap": ICTFairValueGapStrategy(),
    "Wyckoff Spring": WyckoffSpringStrategy(),
    "VWAP Reversion": VWAPReversionStrategy(),
    "BB Squeeze": BollingerSqueezeStrategy(),
    "SuperTrend": SuperTrendMomentumStrategy(),
    "RSI Divergence": RSIDivergenceStrategy(),
    "London Breakout": LondonBreakoutStrategy(),
    "Cross Momentum": CrossMomentumStrategy(),
}

# Maps strategy name → class (not instance) so backtest can create fresh objects each run
STRATEGY_CLASSES = {name: inst.__class__ for name, inst in STRATEGY_MAP.items()}

# All symbols needed across all strategies
ALL_SYMBOLS = list({s for strat in STRATEGY_MAP.values() for s in strat.symbols})


def _close_trade(db, trade, current_price: float):
    if trade.side == "long":
        pnl = (current_price - trade.entry_price) / trade.entry_price * trade.quantity
    else:
        pnl = (trade.entry_price - current_price) / trade.entry_price * trade.quantity

    trade.exit_price = round(current_price, 4)
    trade.realized_pnl = round(pnl, 2)
    trade.status = "closed"
    trade.exit_time = datetime.utcnow()

    analyst = (
        db.query(models.Analyst).filter(models.Analyst.id == trade.analyst_id).first()
    )
    if analyst:
        margin = trade.quantity / trade.leverage
        analyst.current_balance = round(analyst.current_balance + margin + pnl, 2)

        # Snapshot total equity = liquid cash + still-locked margins from other open trades
        # (avoids artificially low snapshots that inflate max_drawdown)
        remaining_open = (
            db.query(models.Trade)
            .filter(models.Trade.analyst_id == analyst.id, models.Trade.status == "open")
            .all()
        )
        locked_margin = sum(t.quantity / (t.leverage or 1) for t in remaining_open)
        total_equity = round(analyst.current_balance + locked_margin, 2)

        db.add(
            models.BalanceSnapshot(
                analyst_id=analyst.id,
                balance=total_equity,
                unrealized_pnl=0.0,
                timestamp=datetime.utcnow(),
            )
        )
    sign = "+" if pnl >= 0 else ""
    print(
        f"  CLOSE {trade.side.upper()} {trade.symbol} @${current_price:,.0f}  PnL={sign}${pnl:.2f}"
    )
    if analyst:
        update_after_close(db, trade, analyst)
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(
                notify_close(
                    analyst.name, analyst.strategy, trade.symbol, trade.side,
                    trade.entry_price, current_price, pnl,
                )
            )
        except Exception:
            pass


def _check_exits(db, current_prices: dict):
    open_trades = db.query(models.Trade).filter(models.Trade.status == "open").all()
    closed = 0
    for trade in open_trades:
        price_data = current_prices.get(trade.symbol)
        if not price_data:
            continue
        price = price_data["price"]
        strategy = STRATEGY_MAP.get(
            db.query(models.Analyst)
            .filter(models.Analyst.id == trade.analyst_id)
            .first()
            .strategy
        )
        if strategy and strategy.should_close(trade, price):
            _close_trade(db, trade, price)
            closed += 1
    return closed


def _bitget_filter(strategy_name: str, signal, bitget_ctx: dict) -> tuple:
    """
    Apply Bitget live market data as a second-pass filter on top of strategy signals.
    Returns (allowed: bool, reason: str).

    Integrated strategies (11 total):
    - Arbitrage: extreme funding blocks opposing direction
    - Macro/Sentiment: crowd positioning blocks trend-following
    - Capital Flow: funding rate confirms or blocks flow direction
    - Whale Hunting: OI appended; extreme funding blocks against squeeze
    - On-chain Data: high funding = speculator overcrowd, block longs
    - SMC: funding rate aligns with smart money direction
    - Liquidity: long/short ratio predicts which stops are denser
    - Wyckoff Spring: crowd imbalance confirms spring reversal
    - Order Flow: funding must align with VDP direction
    - Mean Reversion: extreme funding strengthens contrarian signal
    - Auction Theory: funding + crowd confirms auction balance/imbalance
    """
    if not bitget_ctx or signal.action == "hold":
        return True, ""

    rate = bitget_ctx.get("funding_rate", 0.0)
    long_pct = bitget_ctx.get("long_pct", 50.0)
    short_pct = bitget_ctx.get("short_pct", 50.0)
    oi = bitget_ctx.get("open_interest", 0)
    action = signal.action

    # ── Arbitrage ─────────────────────────────────────────────────────────────
    if strategy_name == "Arbitrage":
        if rate > 0.08 and action == "long":
            return False, f"Bitget funding {rate:+.4f}% — long squeeze risk blocked"
        if rate < -0.04 and action == "short":
            return False, f"Bitget funding {rate:+.4f}% negative — short squeeze risk blocked"

    # ── Macro/Sentiment ────────────────────────────────────────────────────────
    elif strategy_name == "Macro/Sentiment":
        if long_pct > 68 and action == "long":
            return False, f"Bitget crowd {long_pct:.0f}% long — too crowded, blocking long"
        if long_pct < 32 and action == "short":
            return False, f"Bitget crowd {long_pct:.0f}% long — oversold crowd, blocking short"

    # ── Capital Flow ───────────────────────────────────────────────────────────
    elif strategy_name == "Capital Flow":
        if rate > 0.02 and action == "short":
            return False, f"Bitget funding {rate:+.4f}% — capital inflow, blocking short"
        if rate < -0.02 and action == "long":
            return False, f"Bitget funding {rate:+.4f}% — capital outflow, blocking long"

    # ── Whale Hunting ──────────────────────────────────────────────────────────
    elif strategy_name == "Whale Hunting":
        if oi > 0:
            signal.reason += f" | Bitget OI={oi:,.0f} BTC"
        # Extreme funding against position = squeeze risk even for whales
        if rate > 0.10 and action == "long":
            return False, f"Bitget funding {rate:+.4f}% extreme — whale long squeeze risk"
        if rate < -0.05 and action == "short":
            return False, f"Bitget funding {rate:+.4f}% extreme — whale short squeeze risk"

    # ── On-chain Data ──────────────────────────────────────────────────────────
    # High funding = speculators overcrowded on longs → holders' edge eroded
    elif strategy_name == "On-chain Data":
        if rate > 0.06 and action == "long":
            return False, f"Bitget funding {rate:+.4f}% — speculator overleverage, on-chain long blocked"
        if rate < -0.03 and action == "short":
            return False, f"Bitget funding {rate:+.4f}% — short overleverage, on-chain short blocked"

    # ── SMC (Smart Money Concepts) ─────────────────────────────────────────────
    # Smart money typically receives funding → high funding means smart money is short
    elif strategy_name == "SMC":
        if rate > 0.07 and action == "long":
            return False, f"Bitget funding {rate:+.4f}% — smart money likely short, blocking long"
        if rate < -0.04 and action == "short":
            return False, f"Bitget funding {rate:+.4f}% — smart money likely long, blocking short"
        signal.reason += f" | Bitget funding {rate:+.4f}%"

    # ── Liquidity ──────────────────────────────────────────────────────────────
    # >65% longs = dense stops below (bullish sweep more likely to succeed)
    # <35% longs = dense stops above (bearish sweep more likely to succeed)
    elif strategy_name == "Liquidity":
        if action == "long" and long_pct < 40:
            return False, f"Bitget {long_pct:.0f}% long — sparse stop pool below, sweep less likely"
        if action == "short" and long_pct > 60:
            return False, f"Bitget {long_pct:.0f}% long — sparse stop pool above, sweep less likely"
        signal.reason += f" | LSR {long_pct:.0f}%L/{short_pct:.0f}%S"

    # ── Wyckoff Spring ─────────────────────────────────────────────────────────
    # Spring requires crowd to be wrong → contrarian confirmation via LSR
    elif strategy_name == "Wyckoff Spring":
        if action == "long" and long_pct < 38:
            return False, f"Bitget {long_pct:.0f}% long — crowd already short, spring invalid"
        if action == "short" and long_pct > 62:
            return False, f"Bitget {long_pct:.0f}% long — crowd already long, spring invalid"
        signal.reason += f" | Bitget LSR {long_pct:.0f}%L"

    # ── Order Flow ─────────────────────────────────────────────────────────────
    # Funding direction should agree with VDP cross
    elif strategy_name == "Order Flow":
        if action == "long" and rate < -0.03:
            return False, f"Bitget funding {rate:+.4f}% — flow divergence, blocking long"
        if action == "short" and rate > 0.05:
            return False, f"Bitget funding {rate:+.4f}% — flow divergence, blocking short"
        signal.reason += f" | Bitget funding {rate:+.4f}%"

    # ── Mean Reversion ─────────────────────────────────────────────────────────
    # Extreme funding = more fuel for reversion; mild funding = less edge
    elif strategy_name == "Mean Reversion":
        if action == "long" and rate > 0.07:
            # Extreme positive funding = funding squeeze ahead, boosts long reversion
            signal.reason += f" | Bitget funding {rate:+.4f}% (squeeze fuel)"
        elif action == "long" and rate < -0.05:
            return False, f"Bitget funding {rate:+.4f}% — shorts being paid, reversion risk"
        if action == "short" and rate < -0.06:
            signal.reason += f" | Bitget funding {rate:+.4f}% (short squeeze fuel)"
        elif action == "short" and rate > 0.04:
            return False, f"Bitget funding {rate:+.4f}% — longs being paid, reversion risk"

    # ── Auction Theory ─────────────────────────────────────────────────────────
    # Funding confirms auction direction; crowd imbalance signals value area break
    elif strategy_name == "Auction Theory":
        if action == "long" and rate < -0.04:
            return False, f"Bitget funding {rate:+.4f}% — auction selling pressure, blocking long"
        if action == "short" and rate > 0.06:
            return False, f"Bitget funding {rate:+.4f}% — auction buying pressure, blocking short"
        # Crowd imbalance = auction about to break value area
        if long_pct > 65 and action == "long":
            return False, f"Bitget {long_pct:.0f}% long — auction crowd skewed, blocking long"
        signal.reason += f" | Bitget {rate:+.4f}% / {long_pct:.0f}%L"

    return True, ""


async def _run_one_analyst(
    analyst, strategy, ohlcv_map: dict, current_prices: dict, db, bitget_ctx: dict | None = None
):
    """Evaluate signal and optionally open a new position for one analyst."""
    # Risk checks: analyst-level pause + daily loss
    can_trade, reason = check_analyst_can_trade(db, analyst)
    if not can_trade:
        return

    # Count open positions
    open_count = (
        db.query(models.Trade)
        .filter(models.Trade.analyst_id == analyst.id, models.Trade.status == "open")
        .count()
    )
    if open_count >= strategy.max_positions:
        return

    # Build ohlcv subset for this strategy
    strat_ohlcv = {sym: ohlcv_map[sym] for sym in strategy.symbols if sym in ohlcv_map}
    if not strat_ohlcv:
        return

    try:
        signal = strategy.get_signal(strat_ohlcv)
    except Exception as e:
        print(f"  [{analyst.name}] signal error: {e}")
        return

    print(f"  [{analyst.name}] {analyst.strategy} -> {signal.action} | {signal.reason[:60]}")
    if signal.action not in ("long", "short"):
        return

    # Bitget second-pass filter
    if bitget_ctx:
        allowed, block_reason = _bitget_filter(analyst.strategy, signal, bitget_ctx)
        if not allowed:
            print(f"  [{analyst.name}] BLOCKED by Bitget filter: {block_reason}")
            return

    # Use primary symbol for the trade
    primary = strategy.symbols[0]
    price_data = current_prices.get(primary)
    if not price_data:
        return
    current_price = price_data["price"]

    # Avoid duplicate direction on same symbol
    existing = (
        db.query(models.Trade)
        .filter(
            models.Trade.analyst_id == analyst.id,
            models.Trade.status == "open",
            models.Trade.symbol == primary,
            models.Trade.side == signal.action,
        )
        .first()
    )
    if existing:
        return

    # Concentration check: too many analysts same direction same symbol?
    can_add, conc_reason = check_concentration(db, primary, signal.action)
    if not can_add:
        return

    # Position sizing: risk_pct of balance scaled by streak multiplier (no hard cap)
    size_mult = get_size_multiplier(analyst)
    position_size = analyst.current_balance * strategy.risk_pct * size_mult
    margin = position_size / strategy.leverage
    if margin > analyst.current_balance * 0.45 or analyst.current_balance < 500:
        return

    # SL / TP prices
    if signal.action == "long":
        sl = round(current_price * (1 - signal.stop_loss_pct), 4)
        tp = round(current_price * (1 + signal.take_profit_pct), 4)
    else:
        sl = round(current_price * (1 + signal.stop_loss_pct), 4)
        tp = round(current_price * (1 - signal.take_profit_pct), 4)

    trade = models.Trade(
        analyst_id=analyst.id,
        symbol=primary,
        side=signal.action,
        entry_price=round(current_price, 4),
        quantity=round(position_size, 2),
        leverage=strategy.leverage,
        stop_loss=sl,
        take_profit=tp,
        notes=signal.reason,
        status="open",
        entry_time=datetime.utcnow(),
        mode=config.TRADING_MODE,
    )
    db.add(trade)
    analyst.current_balance = round(analyst.current_balance - margin, 2)

    print(
        f"  OPEN  {signal.action.upper():5s} {primary} @${current_price:,.0f}"
        f"  SL=${sl:,.0f}  TP=${tp:,.0f}  [{analyst.name} | {signal.reason[:60]}]"
    )
    try:
        asyncio.create_task(
            notify_open(
                analyst.name, analyst.strategy, primary, signal.action,
                current_price, sl, tp, position_size, signal.reason[:80],
            )
        )
    except Exception:
        pass


async def strategy_engine_loop():
    """Main loop: runs every 5 minutes."""
    print("[strategy_engine] Started - first run in 60s")
    await asyncio.sleep(60)  # brief warm-up after startup

    while True:
        print(f"\n[strategy_engine] Tick {datetime.utcnow().strftime('%H:%M:%S')}")
        db = SessionLocal()
        try:
            current_prices = get_current_prices()
            if not current_prices:
                print("  no price data yet - skipping")
                await asyncio.sleep(300)
                continue

            # Update portfolio + analyst peaks
            analysts = db.query(models.Analyst).all()
            update_portfolio_peak(db, analysts)
            db.commit()

            # Portfolio circuit breaker (40% nuclear last resort — individual analyst protections handle normal cases)
            port_ok, port_msg = check_portfolio_circuit_breaker(db)
            if not port_ok:
                print(f"  [RISK] CIRCUIT BREAKER: {port_msg} - no new trades this tick")

            # Fetch OHLCV for all symbols + Bitget live context in parallel
            ohlcv_map, bitget_ctx = await asyncio.gather(
                get_ohlcv_multi(ALL_SYMBOLS),
                get_market_context(),
                return_exceptions=True,
            )
            if isinstance(ohlcv_map, Exception):
                ohlcv_map = {}
            if isinstance(bitget_ctx, Exception):
                bitget_ctx = {}
            else:
                print(f"  [Bitget] {bitget_ctx.get('summary', 'no data')}")

            # 1. Check exit conditions for all open positions
            closed = _check_exits(db, current_prices)
            if closed:
                db.commit()
                print(f"  Closed {closed} position(s)")

            # 2. Run each analyst's strategy (skip if portfolio circuit breaker active)
            analysts = db.query(models.Analyst).all()
            for analyst in analysts:
                strategy = STRATEGY_MAP.get(analyst.strategy)
                if not strategy:
                    continue
                if port_ok:
                    await _run_one_analyst(analyst, strategy, ohlcv_map, current_prices, db, bitget_ctx)

            db.commit()

        except Exception as e:
            print(f"[strategy_engine] Error: {e}")
            db.rollback()
        finally:
            db.close()

        await asyncio.sleep(300)  # wait 5 minutes
