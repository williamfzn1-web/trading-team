from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, rsi


class OnChainStrategy(BaseStrategy):
    """EMA50 cross in EMA200 trend context — simplified from NUPL/SOPR proxies."""

    name = "On-chain Data"
    symbols = ["BTC/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85
    bypass_trend_filter = False

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 210:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]

        e50 = ema(closes, 50)
        e200 = ema(closes, 200)
        curr_rsi = rsi(closes)
        curr_atr = atr(ohlcv)

        uptrend = curr > e200[-1]
        e50_rising = e50[-1] > e50[-10]
        e50_falling = e50[-1] < e50[-10]

        sl_pct = max(curr_atr * 1.5 / curr, 0.018)
        tp_pct = sl_pct * 3.0

        # LONG: uptrend, EMA50 rising, price dipped below EMA50 in last 3 bars then recovered
        dipped_then_recovered = (
            any(closes[-(i + 1)] < e50[-(i + 1)] for i in range(1, 4))
            and curr > e50[-1]
        )
        if uptrend and e50_rising and dipped_then_recovered and 38 < curr_rsi < 62:
            return Signal(
                "long",
                confidence=0.72,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"EMA50 dip-recover in uptrend, RSI={curr_rsi:.0f}",
            )

        # SHORT: downtrend, EMA50 falling, price bounced above EMA50 in last 3 bars then rejected
        bounced_then_rejected = (
            any(closes[-(i + 1)] > e50[-(i + 1)] for i in range(1, 4))
            and curr < e50[-1]
        )
        if not uptrend and e50_falling and bounced_then_rejected and 38 < curr_rsi < 62:
            return Signal(
                "short",
                confidence=0.70,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"EMA50 bounce-reject in downtrend, RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"NUPL={((curr - e200[-1]) / e200[-1]):.3f}, uptrend={uptrend}",
        )
