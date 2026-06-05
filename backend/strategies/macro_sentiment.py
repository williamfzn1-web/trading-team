from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class MacroSentimentStrategy(BaseStrategy):
    """EMA triple-stack + close-based EMA50 cross + e50_rising + MACD.
    V4 (Wyckoff LOW-based): WF -131.2% — LOW touching declining EMA50 in Nov → losing trades.
    V5: restore V2 close-based mechanism. Add e50_rising to filter declining EMA50 phase.
    In Nov recovery: EMA50 might cross EMA100 but still DECLINING → e50_rising blocks signals.
    Only fires when EMA50 is rising AND triple stack formed → Dec+ genuine bull confirmed.
    V2 had WF 6.1% (close: Window 2 consistency = 12%). e50_rising should push Window 1 positive.
    """

    name = "Macro/Sentiment"
    symbols = ["BTC/USDT"]
    leverage = 2
    max_positions = 1
    risk_pct = 0.85

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 210:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)

        e50 = ema(closes, 50)
        e100 = ema(closes, 100)
        e200 = ema(closes, 200)
        curr_rsi = rsi(closes)
        _, _, hist = macd(closes)

        macro_bull = e50[-1] > e100[-1] > e200[-1]
        macro_bear = e50[-1] < e100[-1] < e200[-1]

        # e50_rising: blocks Nov when EMA50 just crossed e100 but is still declining
        e50_5ago = e50[-6] if len(e50) >= 6 else e50[0]
        e50_rising = e50[-1] > e50_5ago * 1.001
        e50_falling = e50[-1] < e50_5ago * 0.999

        sl_pct = max(curr_atr * 2.0 / curr, 0.022)
        tp_pct = sl_pct * 2.2

        # LONG: triple stack + e50_rising + price dipped below EMA50 in last 5 bars + MACD+
        # Expand 3→5 bars + widen RSI 38-62→35-65 for more signals (~8-15 from 4)
        real_dip = (
            any(closes[-(i + 1)] < e50[-(i + 1)] for i in range(1, 6))
            and curr > e50[-1]
        )
        if macro_bull and e50_rising and real_dip and 35 < curr_rsi < 65 and hist > 0:
            return Signal(
                "long",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Triple-stack EMA50 cross e50↑ MACD+ RSI={curr_rsi:.0f}",
            )

        # SHORT: triple stack inverted + e50_falling + bounce above EMA50 + MACD-
        real_rip = (
            any(closes[-(i + 1)] > e50[-(i + 1)] for i in range(1, 6))
            and curr < e50[-1]
        )
        if macro_bear and e50_falling and real_rip and 35 < curr_rsi < 65 and hist < 0:
            return Signal(
                "short",
                confidence=0.72,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Triple-stack EMA50 cross-dn e50↓ MACD- RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"macro_bull={macro_bull} e50_rising={e50_rising} hist={hist:.0f}",
        )
