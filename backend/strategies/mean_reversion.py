from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, bollinger, ema, rsi


class MeanReversionStrategy(BaseStrategy):
    """Bollinger Band extreme touch + RSI reversal candle confirmation."""

    name = "Mean Reversion"
    symbols = ["ETH/USDT", "SOL/USDT", "BNB/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("ETH/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 50:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        rsi_prev = rsi(closes[:-3])

        bb_up, bb_mid, bb_lo = bollinger(closes, period=20, mult=1.8)

        # Require previous close to have touched the band (not just current)
        prev_close = closes[-2]
        touched_lo = prev_close <= bb_lo or curr <= bb_lo
        touched_hi = prev_close >= bb_up or curr >= bb_up

        reversal_bull = ohlcv[-1][4] > ohlcv[-1][1]  # green candle
        reversal_bear = ohlcv[-1][4] < ohlcv[-1][1]  # red candle

        sl_pct = max(curr_atr * 1.2 / curr, 0.012)
        tp_pct = (
            max((bb_mid - curr) / curr, sl_pct * 2.0) if curr < bb_mid else sl_pct * 2.5
        )

        if touched_lo and curr_rsi < 36 and curr_rsi > rsi_prev and reversal_bull:
            pct = (bb_lo - curr) / bb_lo * 100
            return Signal(
                "long",
                confidence=0.76,
                stop_loss_pct=sl_pct,
                take_profit_pct=abs(tp_pct),
                reason=f"BB lower extreme RSI={curr_rsi:.0f} recovering, {pct:.1f}% below band",
            )

        tp_pct_s = (
            max((curr - bb_mid) / curr, sl_pct * 2.0) if curr > bb_mid else sl_pct * 2.5
        )
        if touched_hi and curr_rsi > 64 and curr_rsi < rsi_prev and reversal_bear:
            pct = (curr - bb_up) / bb_up * 100
            return Signal(
                "short",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=abs(tp_pct_s),
                reason=f"BB upper extreme RSI={curr_rsi:.0f} fading, {pct:.1f}% above band",
            )

        bb_pos = (curr - bb_lo) / (bb_up - bb_lo + 1e-9)
        return Signal("hold", reason=f"RSI={curr_rsi:.0f} BB_pos={bb_pos:.2f}")
