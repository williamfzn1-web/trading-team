from strategies.base import BaseStrategy, Signal
from strategies.indicators import adx, atr, ema, rsi


class SMCStrategy(BaseStrategy):
    """Donchian Channel breakout with 2-bar close confirmation to filter false breakouts."""

    name = "SMC"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 2
    max_positions = 1
    risk_pct = 0.05  # WF -22%, still negative
    bypass_trend_filter = True  # internal uptrend/downtrend check handles this

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]

        curr_atr = atr(ohlcv)
        prev_atr = atr(ohlcv[:-10])
        atr_expand = curr_atr > prev_atr * 1.15

        curr_rsi = rsi(closes)
        curr_adx = adx(ohlcv)
        e200 = ema(closes, 200)
        uptrend = curr > e200[-1]

        avg_vol = sum(vols[-20:]) / 20
        vol_conf = vols[-1] > avg_vol * 2.0

        if curr_adx < 20:
            return Signal("hold", reason=f"ADX={curr_adx:.1f} < 20, ranging market")

        # 40-bar Donchian (exclude current bar)
        dc_high = max(closes[-41:-1])
        dc_low = min(closes[-41:-1])

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0

        # LONG: current bar breaks out AND previous bar was near the breakout level (within 1%)
        near_high = closes[-2] >= dc_high * 0.990
        if (
            curr > dc_high
            and near_high
            and vol_conf
            and atr_expand
            and uptrend
            and 50 < curr_rsi < 78
        ):
            return Signal(
                "long",
                confidence=0.82,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"40-bar breakout {dc_high:,.0f} vol={vols[-1]/avg_vol:.1f}x ATR+",
            )

        # SHORT: current bar breaks down AND previous bar was near the breakdown level (within 1%)
        near_low = closes[-2] <= dc_low * 1.010
        if (
            curr < dc_low
            and near_low
            and vol_conf
            and atr_expand
            and not uptrend
            and 22 < curr_rsi < 50
        ):
            return Signal(
                "short",
                confidence=0.80,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"40-bar breakdown {dc_low:,.0f} vol={vols[-1]/avg_vol:.1f}x ATR+",
            )

        return Signal(
            "hold", reason=f"DC40=[{dc_low:,.0f}-{dc_high:,.0f}] RSI={curr_rsi:.0f}"
        )
