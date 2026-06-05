from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class WyckoffSpringStrategy(BaseStrategy):
    """Wyckoff EMA50 Bounce V11 — Add SOL for more opportunities + volume surge filter.
    V6 (BTC/ETH): +10.05%, 27.27% WR, 33 trades.
    Add SOL/USDT for more EMA50 bounce opportunities.
    Add volume surge confirmation (vols[-1] > avg_vol * 1.2) to improve WR.
    Target: 45+ trades, 35%+ WR → 20%+ return."""

    name = "Wyckoff Spring"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 3
    risk_pct = 0.85

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        _, _, hist = macd(closes)

        e200 = ema(closes, 200)
        e50 = ema(closes, 50)
        macro_up = curr > e200[-1] and e50[-1] > e200[-1]
        macro_dn = curr < e200[-1] and e50[-1] < e200[-1]

        e50_val = e50[-1]
        avg_vol = sum(vols[-20:]) / 20
        last = ohlcv[-1]
        prev = ohlcv[-2]

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.5

        # LONG: price touched EMA50 zone + bullish bounce + volume surge + MACD+
        touched_e50 = any(
            e50[-(i + 1)] * 0.990 <= ohlcv[-(i + 1)][3] <= e50[-(i + 1)] * 1.012
            for i in range(1, 5)
            if i + 1 <= len(e50)
        )
        bullish_bounce = last[4] > e50_val and last[4] > last[1]
        vol_bounce = vols[-1] > avg_vol * 1.2  # volume confirms the bounce

        if (
            macro_up
            and touched_e50
            and bullish_bounce
            and vol_bounce
            and 30 < curr_rsi < 56
            and hist > 0
        ):
            return Signal(
                "long",
                confidence=0.84,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] EMA50 bounce vol×{vols[-1]/avg_vol:.1f} RSI={curr_rsi:.0f} MACD+",
            )

        # SHORT: touched EMA50 from below (resistance) + bearish rejection + volume
        touched_e50_dn = any(
            e50[-(i + 1)] * 0.988 <= ohlcv[-(i + 1)][2] <= e50[-(i + 1)] * 1.010
            for i in range(1, 5)
            if i + 1 <= len(e50)
        )
        bearish_rejection = last[4] < e50_val and last[4] < last[1]

        if (
            macro_dn
            and touched_e50_dn
            and bearish_rejection
            and vol_bounce
            and 44 < curr_rsi < 70
            and hist < 0
        ):
            return Signal(
                "short",
                confidence=0.84,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] EMA50 reject vol×{vols[-1]/avg_vol:.1f} RSI={curr_rsi:.0f} MACD-",
            )

        return Signal(
            "hold",
            reason=f"[{symbol}] No EMA50 bounce touch={touched_e50} RSI={curr_rsi:.0f}",
        )

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No EMA50 test on BTC/ETH/SOL")
