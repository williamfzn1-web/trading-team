from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class SuperTrendMomentumStrategy(BaseStrategy):
    """SuperTrend V9 — Deep RSI Oversold Bounce in Confirmed Uptrend.
    Inspired by Cross Momentum (50% WR) and VWAP (40% WR) patterns.
    Core: RSI < 35 + uptrend confirmed + price bouncing + MACD not severely negative.
    Adds SOL for more opportunities. Targets 10-15 trades with 40%+ WR."""

    name = "SuperTrend"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 3
    risk_pct = 0.85

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 55:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        _, _, hist = macd(closes)

        e200 = ema(closes, 200)
        e50 = ema(closes, 50)
        macro_up = curr > e200[-1] and e50[-1] > e200[-1]
        macro_dn = curr < e200[-1] and e50[-1] < e200[-1]

        r120 = (closes[-1] - closes[-121]) / closes[-121] if len(closes) > 121 else 0

        last = ohlcv[-1]
        prev = ohlcv[-2]
        bullish_bar = last[4] > last[1]
        bearish_bar = last[4] < last[1]
        price_recovering = last[4] > prev[4]
        price_falling = last[4] < prev[4]

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.5

        # LONG: deep oversold in uptrend + bouncing + MACD not severely broken
        if (
            macro_up
            and r120 > 0.03
            and curr_rsi < 35
            and price_recovering
            and bullish_bar
            and hist > -200  # MACD histogram not deeply negative
        ):
            return Signal(
                "long",
                confidence=min(0.76 + (35 - curr_rsi) * 0.012, 0.92),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] Deep oversold bounce RSI={curr_rsi:.0f} 5d={r120*100:.1f}%",
            )

        # SHORT: deep overbought in downtrend + reversing
        if (
            macro_dn
            and r120 < -0.03
            and curr_rsi > 65
            and price_falling
            and bearish_bar
            and hist < 200
        ):
            return Signal(
                "short",
                confidence=min(0.76 + (curr_rsi - 65) * 0.012, 0.92),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] Overbought reversal RSI={curr_rsi:.0f} 5d={r120*100:.1f}%",
            )

        return Signal(
            "hold", reason=f"[{symbol}] RSI={curr_rsi:.0f} r120={r120*100:.1f}%"
        )

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No deep oversold bounce on BTC/ETH/SOL")
