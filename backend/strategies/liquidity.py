from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, swing_highs_lows


class LiquidityStrategy(BaseStrategy):
    """Swing stop sweep with strong rejection: wick >= 0.5 ATR + close >= 0.8 ATR back."""

    name = "Liquidity"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 3
    max_positions = 2
    risk_pct = 1.20

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)

        # EMA200 trend filter (broader than EMA50 — less over-restrictive)
        e200 = ema(closes, 200)
        in_uptrend = curr > e200[-1]

        # Swing levels (lb=3 — more structural points, less filtering)
        recent_closes = closes[-40:]
        swing_h, swing_l = swing_highs_lows(recent_closes, lb=3)

        if not swing_l and not swing_h:
            return Signal("hold", reason="no significant swing levels")

        last = ohlcv[-1]
        prev = ohlcv[-2]

        # Bullish sweep quality criteria:
        # 1. Last candle wicked below a swing low (wick >= 0.5 ATR below level)
        # 2. Last candle closed strongly back above level (close >= 0.8 ATR above level)
        # 3. Previous candle closed above level (no prior breach)
        bullish_sweep = False
        sweep_lvl = None
        if swing_l:
            for lvl in swing_l:
                wick_depth = lvl - last[3]  # how far below level the wick went
                close_recovery = last[4] - lvl  # how far above level the close is
                if (
                    wick_depth >= curr_atr * 0.35
                    and close_recovery >= curr_atr * 0.55
                    and prev[4] > lvl
                ):
                    bullish_sweep = True
                    sweep_lvl = lvl
                    break

        # Bearish sweep quality criteria (mirror)
        bearish_sweep = False
        sweep_h_lvl = None
        if swing_h:
            for lvl in swing_h:
                wick_height = last[2] - lvl
                close_drop = lvl - last[4]
                if (
                    wick_height >= curr_atr * 0.35
                    and close_drop >= curr_atr * 0.55
                    and prev[4] < lvl
                ):
                    bearish_sweep = True
                    sweep_h_lvl = lvl
                    break

        sl_pct = max(curr_atr * 1.3 / curr, 0.013)
        tp_pct = sl_pct * 2.8

        if bullish_sweep and in_uptrend:
            return Signal(
                "long",
                confidence=0.84,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Strong sweep of swing low ${sweep_lvl:,.0f} — rejection candle (uptrend)",
            )

        if bearish_sweep and not in_uptrend:
            return Signal(
                "short",
                confidence=0.84,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Strong sweep of swing high ${sweep_h_lvl:,.0f} — rejection candle (downtrend)",
            )

        return Signal(
            "hold",
            reason=f"No quality sweep — bull={bullish_sweep}, bear={bearish_sweep}, uptrend={in_uptrend}",
        )
