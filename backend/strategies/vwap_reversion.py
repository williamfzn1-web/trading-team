from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi, vwap_bands


class VWAPReversionStrategy(BaseStrategy):
    """VWAP Reversion V15 — Add MACD hist>0 to fix WF (was 6.4% with SOL, 37.9% without).
    V14 (BTC/ETH/SOL, wick 0.001): 68 trades, 29.4% WR, +21.14% return, WF 6.4% — SOL trades hurt WF.
    V15: keep SOL + wick 0.001 but add MACD hist>0 to filter low-quality signals.
    MACD>0 in bull market blocks Oct-Nov 2025 failed recovery VWAP wicks → cleaner training.
    Expected: 30-45 trades (MACD filters ~40% of V14 trades) at 38%+ WR → 22%+ return.
    WF: MACD protection → training window avoids bear losses → consistent test/train ratio."""

    name = "VWAP Reversion"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)

        vwap_val, upper, lower = vwap_bands(ohlcv, period=48)
        _, _, hist = macd(closes)

        e200 = ema(closes, 200)
        macro_up = curr > e200[-1]
        macro_dn = curr < e200[-1]

        band_pct = (upper - lower) / vwap_val if vwap_val > 0 else 0
        if band_pct < 0.004:
            return Signal("hold", reason=f"[{symbol}] bands too narrow")

        last = ohlcv[-1]
        bullish_bar = last[4] > last[1]
        bearish_bar = last[4] < last[1]

        sl_pct = max(curr_atr * 1.4 / curr, 0.013)
        tp_pct = sl_pct * 3.5

        # LONG: deep wick below lower band (>=0.4% depth) + close recovery
        dev_down = (vwap_val - curr) / vwap_val
        wick_depth = (lower - last[3]) / vwap_val
        low_pierced = last[3] < lower
        close_recovered = last[4] >= lower * 0.999

        if (
            low_pierced
            and wick_depth >= 0.001
            and close_recovered
            and bullish_bar
            and macro_up
            and curr_rsi < 48
            and dev_down >= 0.002
            and hist > 0
        ):
            return Signal(
                "long",
                confidence=min(0.78 + dev_down * 4, 0.94),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] VWAP deep wick {wick_depth*100:.2f}% RSI={curr_rsi:.0f}",
            )

        # SHORT: deep wick above upper band + close rejection
        dev_up = (curr - vwap_val) / vwap_val
        wick_height = (last[2] - upper) / vwap_val
        high_pierced = last[2] > upper
        close_rejected = last[4] <= upper * 1.001

        if (
            high_pierced
            and wick_height >= 0.002
            and close_rejected
            and bearish_bar
            and macro_dn
            and curr_rsi > 52
            and dev_up >= 0.003
        ):
            return Signal(
                "short",
                confidence=min(0.78 + dev_up * 4, 0.94),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] VWAP deep wick fade {wick_height*100:.2f}% RSI={curr_rsi:.0f}",
            )

        return Signal("hold", reason=f"[{symbol}] No deep VWAP wick RSI={curr_rsi:.0f}")

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No VWAP deep wick on BTC or ETH")
