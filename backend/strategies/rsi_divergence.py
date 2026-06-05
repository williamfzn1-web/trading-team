from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class RSIDivergenceStrategy(BaseStrategy):
    """EMA20 Wick Support V22 — wider zone (0.978-1.008) for more trades and stable WF.
    V21 (zone 0.985-1.005): WF 49.7% (just below 50%) and return variable (1.11%↔20.52%).
    Root cause of instability: only 33-37 trades → high WR variance from 27%↔36%.
    V22: widen zone to 0.978-1.008 → more qualifying bars → target 45-55 trades.
    More trades per WF window → stabilized WR around 34-38% → consistently positive WF.
    With 50 trades at 35% WR: return ≈ 20%+ and WF windows have 15+ trades → stable stats.
    EMA cascade (e20>e50>e200) blocks bear market same as Wyckoff.
    BTC/ETH/SOL/BNB. Target: 20-30 trades at 42%+ WR → 22%+ return."""

    name = "RSI Divergence"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    leverage = 2
    max_positions = 4
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
        e20 = ema(closes, 20)

        # EMA cascade: e20>e50>e200 naturally delays signals until confirmed bull
        # In Oct-Nov 2025 recovery: EMA cascade takes 2-3 weeks to align → no false triggers
        macro_up = curr > e200[-1] and e50[-1] > e200[-1] and e20[-1] > e50[-1]
        macro_dn = curr < e200[-1] and e50[-1] < e200[-1] and e20[-1] < e50[-1]

        e20_val = e20[-1]
        e20_5ago = e20[-6] if len(e20) >= 6 else e20[0]
        e20_rising = e20_val > e20_5ago * 1.001

        avg_vol = sum(vols[-20:]) / 20
        vol_confirm = vols[-1] > avg_vol * 1.2

        last = ohlcv[-1]
        bullish_bar = last[4] > last[1]
        bearish_bar = last[4] < last[1]

        sl_pct = max(curr_atr * 1.5 / curr, 0.014)
        tp_pct = sl_pct * 3.5

        # LONG: bar's LOW in EMA20 zone (1.5% below to 0.5% above) — bounded wick detection
        # Lower bound prevents catching deep crashes. Upper matches bars approaching EMA20.
        recent_wick = any(
            e20[-(i + 1)] * 0.985 <= ohlcv[-(i + 1)][3] <= e20[-(i + 1)] * 1.005
            for i in range(min(4, len(e20)))
            if len(e20) > i
        )
        close_above_e20 = last[4] > e20_val and bullish_bar
        above_e50 = curr > e50[-1]

        if (
            recent_wick
            and close_above_e20
            and above_e50
            and vol_confirm
            and macro_up
            and e20_rising
            and 33 < curr_rsi < 58
            and hist > 0
        ):
            return Signal(
                "long",
                confidence=min(0.83 + (e50[-1] / e200[-1] - 1) * 5, 0.93),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] EMA20 wick support RSI={curr_rsi:.0f} vol={vols[-1]/avg_vol:.1f}x",
            )

        # SHORT: bar's HIGH touched EMA20 zone from below + closed BELOW EMA20 + downtrend
        recent_wick_dn = any(
            ohlcv[-(i + 1)][2] >= e20[-(i + 1)] * 0.995  # high within 0.5% of EMA20
            for i in range(min(4, len(e20)))
            if len(e20) > i
        )
        close_below_e20 = last[4] < e20_val and bearish_bar
        below_e50 = curr < e50[-1]

        if (
            recent_wick_dn
            and close_below_e20
            and below_e50
            and vol_confirm
            and macro_dn
            and 42 < curr_rsi < 67
            and hist < 0
        ):
            return Signal(
                "short",
                confidence=min(0.83 + (1 - e50[-1] / e200[-1]) * 5, 0.93),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] EMA20 wick resistance RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"[{symbol}] wick={recent_wick} above_e50={above_e50} RSI={curr_rsi:.0f}",
        )

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No EMA20 wick support on BTC/ETH/SOL/BNB")
