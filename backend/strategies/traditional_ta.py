from strategies.base import BaseStrategy, Signal
from strategies.indicators import adx, atr, ema, rsi


class TraditionalTAStrategy(BaseStrategy):
    """EMA50 pullback: price must actually close below EMA50 then recover above it."""

    name = "Traditional TA"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 3
    max_positions = 2
    risk_pct = 0.05  # WF -91%, persistent overfit

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 210:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]

        e20 = ema(closes, 20)
        e50 = ema(closes, 50)
        e200 = ema(closes, 200)
        curr_rsi = rsi(closes)
        rsi_prev = rsi(closes[:-3])
        curr_atr = atr(ohlcv)
        curr_adx = adx(ohlcv)

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0

        if curr_adx < 22:
            return Signal("hold", reason=f"Choppy market ADX={curr_adx:.1f} < 22")

        avg_vol = sum(vols[-20:]) / 20
        vol_spike = vols[-1] > avg_vol * 1.35

        ema_bull = e20[-1] > e50[-1] > e200[-1]
        ema_bear = e20[-1] < e50[-1] < e200[-1]

        # LONG: price actually closed below EMA50 in last 5 bars and is now above it
        confirmed_pullback = (
            any(closes[-(i + 1)] < e50[-(i + 1)] for i in range(1, 6))
            and curr > e50[-1]
        )
        if (
            ema_bull
            and confirmed_pullback
            and vol_spike
            and 40 < curr_rsi < 62
            and curr_rsi > rsi_prev
        ):
            return Signal(
                "long",
                confidence=0.76,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"EMA50 pullback confirmed+vol {vols[-1]/avg_vol:.1f}x, RSI={curr_rsi:.0f}",
            )

        # SHORT: price actually closed above EMA50 in last 5 bars and is now below it
        confirmed_rejection = (
            any(closes[-(i + 1)] > e50[-(i + 1)] for i in range(1, 6))
            and curr < e50[-1]
        )
        if (
            ema_bear
            and confirmed_rejection
            and vol_spike
            and 38 < curr_rsi < 60
            and curr_rsi < rsi_prev
        ):
            return Signal(
                "short",
                confidence=0.70,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"EMA50 rejection confirmed+vol {vols[-1]/avg_vol:.1f}x, RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"RSI={curr_rsi:.0f}, vol_spike={vol_spike}, ema_bull={ema_bull}",
        )
