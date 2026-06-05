from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class ICTFairValueGapStrategy(BaseStrategy):
    """ICT Fair Value Gap — institutional imbalance zones.

    V23: EMA cascade e20>e50>e200 + r168>0. WF -0.719.
         Training caught Dec bull, test hit Mar correction, strategy still longing -> inverts.
    V4.1 minimal fix:
        - EMA cascade replaced with EMA20/50 only (drop EMA200 requirement).
          EMA50 crosses in ~2 weeks vs EMA200 in ~2 months: catches trend reversals faster.
        - r168 removed: redundant with EMA20/50 direction, was causing WF divergence.
        - RSI range kept at 42-60 / 40-58: proven working, no changes.
        - FVG window kept at 24 bars, size threshold 0.001: proven working.
        - TP raised 3.5x -> 4.0x for better EV per trade.
        - risk_pct stays 0.85: 0.95/leverage=2 gives margin=0.475>0.45 cap -> all trades blocked.
    """

    name = "ICT Fair Value Gap"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    leverage = 2
    max_positions = 3
    risk_pct = 0.85

    def _find_fvgs(self, ohlcv: list, curr_price: float):
        avg_vol = sum(c[5] for c in ohlcv[-20:]) / 20
        bull, bear = [], []
        recent = ohlcv[-24:]
        for i in range(1, len(recent) - 1):
            mid_vol = recent[i][5]
            gap_lo = recent[i - 1][2]
            gap_hi = recent[i + 1][3]
            if gap_hi > gap_lo:
                size_pct = (gap_hi - gap_lo) / curr_price
                if size_pct >= 0.001 and mid_vol > avg_vol * 1.1:
                    bull.append((gap_lo, gap_hi))
            gap_hi2 = recent[i - 1][3]
            gap_lo2 = recent[i + 1][2]
            if gap_hi2 > gap_lo2:
                size_pct = (gap_hi2 - gap_lo2) / curr_price
                if size_pct >= 0.001 and mid_vol > avg_vol * 1.1:
                    bear.append((gap_lo2, gap_hi2))
        return bull, bear

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 80:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        rsi_3ago = rsi(closes[:-3]) if len(closes) > 17 else curr_rsi
        _, _, hist = macd(closes)

        # V4.1 key change: EMA20/50 only (drop EMA200 requirement)
        e50 = ema(closes, 50)
        e20 = ema(closes, 20)
        uptrend = curr > e50[-1] and e20[-1] > e50[-1]
        downtrend = curr < e50[-1] and e20[-1] < e50[-1]

        last = ohlcv[-1]
        prev = ohlcv[-2]
        bull_fvgs, bear_fvgs = self._find_fvgs(ohlcv, curr)

        sl_pct = max(curr_atr * 1.5 / curr, 0.014)
        tp_pct = sl_pct * 4.0  # raised from 3.5x

        rsi_rising = curr_rsi > rsi_3ago
        rsi_falling = curr_rsi < rsi_3ago

        for fvg_lo, fvg_hi in reversed(bull_fvgs):
            prev_in_gap = fvg_lo <= prev[3] <= fvg_hi or fvg_lo <= prev[4] <= fvg_hi
            curr_above_gap = last[4] > fvg_hi * 1.001
            if (
                prev_in_gap
                and curr_above_gap
                and uptrend
                and 42 < curr_rsi < 60  # unchanged from V23
                and rsi_rising
                and hist > 0
                and last[4] > last[1]
            ):
                gap_pct = (fvg_hi - fvg_lo) / curr
                return Signal(
                    "long",
                    confidence=min(0.80 + gap_pct * 4, 0.93),
                    stop_loss_pct=sl_pct,
                    take_profit_pct=tp_pct,
                    reason=f"[{symbol}] Bull FVG exit >${fvg_hi:,.0f} RSI={curr_rsi:.0f}",
                )

        for fvg_lo2, fvg_hi2 in reversed(bear_fvgs):
            prev_in_gap = fvg_lo2 <= prev[2] <= fvg_hi2 or fvg_lo2 <= prev[4] <= fvg_hi2
            curr_below_gap = last[4] < fvg_lo2 * 0.999
            if (
                prev_in_gap
                and curr_below_gap
                and downtrend
                and 40 < curr_rsi < 58  # unchanged from V23
                and rsi_falling
                and hist < 0
                and last[4] < last[1]
            ):
                gap_pct = (fvg_hi2 - fvg_lo2) / curr
                return Signal(
                    "short",
                    confidence=min(0.80 + gap_pct * 4, 0.93),
                    stop_loss_pct=sl_pct,
                    take_profit_pct=tp_pct,
                    reason=f"[{symbol}] Bear FVG exit <${fvg_lo2:,.0f} RSI={curr_rsi:.0f}",
                )

        return Signal(
            "hold",
            reason=f"[{symbol}] No FVG exit bull={len(bull_fvgs)} bear={len(bear_fvgs)}",
        )

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No FVG exit on BTC/ETH/SOL/BNB")
