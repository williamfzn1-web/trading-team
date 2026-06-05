from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, rsi


class OrderBookImbalanceStrategy(BaseStrategy):
    """RSI divergence + Stochastic cross: price makes new extreme but momentum reverses."""

    name = "Order Book Imbalance"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    @staticmethod
    def _stoch_rsi(closes: list, period: int = 14) -> float:
        """Stochastic RSI: where is current RSI within its recent range."""
        if len(closes) < period * 2:
            return 50.0
        rsi_vals = []
        for i in range(period, len(closes) + 1):
            subset = closes[:i]
            gains = [max(subset[j] - subset[j - 1], 0) for j in range(1, len(subset))][
                -period:
            ]
            losses = [max(subset[j - 1] - subset[j], 0) for j in range(1, len(subset))][
                -period:
            ]
            ag, al = sum(gains) / period, sum(losses) / period
            r = 100 - 100 / (1 + ag / al) if al > 0 else 100.0
            rsi_vals.append(r)
        if len(rsi_vals) < period:
            return 50.0
        recent = rsi_vals[-period:]
        lo, hi = min(recent), max(recent)
        return (rsi_vals[-1] - lo) / (hi - lo) * 100 if hi > lo else 50.0

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        rsi_prev = rsi(closes[:-5])

        stoch = self._stoch_rsi(closes[-40:])
        stoch_p = self._stoch_rsi(closes[-45:-5])

        e200 = ema(closes, 200)
        uptrend = curr > e200[-1]

        sl_pct = max(curr_atr * 1.3 / curr, 0.013)
        tp_pct = sl_pct * 2.5

        # Bullish divergence: price at recent low but RSI + StochRSI turning up
        recent_low = min(closes[-10:])
        price_at_low = curr <= recent_low * 1.005
        rsi_diverge_bull = curr_rsi > rsi_prev and stoch > stoch_p and stoch < 30

        if price_at_low and rsi_diverge_bull and uptrend:
            return Signal(
                "long",
                confidence=0.76,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Bullish div: price@low RSI={curr_rsi:.0f}↑ StochRSI={stoch:.0f}↑",
            )

        # Bearish divergence: price at recent high but RSI + StochRSI turning down
        recent_high = max(closes[-10:])
        price_at_high = curr >= recent_high * 0.995
        rsi_diverge_bear = curr_rsi < rsi_prev and stoch < stoch_p and stoch > 70

        if price_at_high and rsi_diverge_bear and not uptrend:
            return Signal(
                "short",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Bearish div: price@high RSI={curr_rsi:.0f}↓ StochRSI={stoch:.0f}↓",
            )

        return Signal(
            "hold",
            reason=f"RSI={curr_rsi:.0f} StochRSI={stoch:.0f} uptrend={uptrend}",
        )
