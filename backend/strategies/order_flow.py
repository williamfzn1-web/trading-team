from strategies.base import BaseStrategy, Signal
from strategies.indicators import adx, atr, ema, rsi, volume_delta_proxy


class OrderFlowStrategy(BaseStrategy):
    """VDP zero-cross at EMA50 with structural trend + ADX regime filter."""

    name = "Order Flow"
    symbols = ["ETH/USDT", "BTC/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("ETH/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 210:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]

        curr_atr = atr(ohlcv)
        e200 = ema(closes, 200)
        e50 = ema(closes, 50)
        curr_adx = adx(ohlcv)

        # Structural trend: EMA50 must be above/below EMA200 (not just price)
        uptrend = e50[-1] > e200[-1]
        downtrend = e50[-1] < e200[-1]

        # EMA50 direction confirmed over 20 bars (was 8 — too noisy)
        e50_rising = e50[-1] > e50[-20]
        e50_falling = e50[-1] < e50[-20]

        # VDP zero-cross with 10-bar lookback (was 5 — too short on 1h)
        vdp_now = volume_delta_proxy(ohlcv, 14)
        vdp_prev = volume_delta_proxy(ohlcv[:-10], 14)
        vdp_crossed_up = vdp_prev < 0 and vdp_now > 0
        vdp_crossed_down = vdp_prev > 0 and vdp_now < 0

        curr_rsi = rsi(closes)

        sl_pct = max(curr_atr * 2.0 / curr, 0.018)
        tp_pct = max(curr_atr * 4.5 / curr, 0.045)

        near_ema50 = e50[-1] * 0.988 <= curr <= e50[-1] * 1.012

        # ADX > 18 ensures we're in a trending regime — avoids EMA50 "support" in choppy markets
        if curr_adx < 18:
            return Signal("hold", reason=f"ADX={curr_adx:.1f} < 18, no trend")

        # LONG: structural uptrend + ADX confirmed + VDP cross + EMA50 zone
        if (
            vdp_crossed_up
            and near_ema50
            and uptrend
            and e50_rising
            and 35 < curr_rsi < 62
        ):
            return Signal(
                "long",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"VDP 0-cross up at EMA50, ADX={curr_adx:.0f}, RSI={curr_rsi:.0f}",
            )

        # SHORT: structural downtrend + ADX confirmed + VDP cross + EMA50 zone
        if (
            vdp_crossed_down
            and near_ema50
            and downtrend
            and e50_falling
            and 38 < curr_rsi < 65
        ):
            return Signal(
                "short",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"VDP 0-cross down at EMA50, ADX={curr_adx:.0f}, RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"VDP={vdp_now:.0f}, near_e50={near_ema50}, uptrend={uptrend}, ADX={curr_adx:.1f}",
        )
