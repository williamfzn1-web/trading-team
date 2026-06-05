from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, candle_hour_utc, ema, macd, rsi


class LondonBreakoutStrategy(BaseStrategy):
    """London Session Breakout V22 — new 6-bar high during London open + EMA cascade.
    V20 (RSI recovery + MACD): 27 trades, 29.63% WR, +2.06%, WF -49.3% — WR too low.
    V22: completely different mechanism. Price breaks above last 6-bar high during London (7-10 UTC).
    Classic London breakout: Asian range forms 7h before London, London opens with directional move.
    EMA cascade (e20>e50>e200) blocks Oct-Nov bear recovery false breakouts.
    Volume surge 1.25× confirms institutional momentum (London = highest-volume session).
    RSI 45-68 ensures we're in momentum state, not overbought.
    BTC/ETH/SOL. Target: 15-25 trades at 42%+ WR → 22%+ return."""

    name = "London Breakout"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 3
    risk_pct = 0.85

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 80:
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

        # EMA cascade blocks Oct-Nov 2025 recovery (takes 2-3 weeks to align post-bear)
        macro_up = curr > e200[-1] and e50[-1] > e200[-1] and e20[-1] > e50[-1]
        macro_dn = curr < e200[-1] and e50[-1] < e200[-1] and e20[-1] < e50[-1]

        curr_hour = candle_hour_utc(ohlcv[-1])
        if curr_hour not in {7, 8, 9, 10}:
            return Signal("hold", reason=f"[{symbol}] Not London hours")

        avg_vol = sum(vols[-20:]) / 20
        vol_surge = vols[-1] > avg_vol * 1.25

        last = ohlcv[-1]
        bullish_bar = last[4] > last[1]
        bearish_bar = last[4] < last[1]

        sl_pct = max(curr_atr * 1.5 / curr, 0.014)
        tp_pct = sl_pct * 3.5

        # LONG: price breaks above last 6-bar high (Asian range breakout) during London
        # 6 bars = 6 hours prior = Asian session range
        session_high = max(c[2] for c in ohlcv[-7:-1])  # high of last 6 bars
        breakout_up = last[4] > session_high and last[2] > session_high

        if (
            breakout_up
            and vol_surge
            and macro_up
            and 45 < curr_rsi < 68
            and bullish_bar
            and hist > 0
        ):
            return Signal(
                "long",
                confidence=min(
                    0.82 + (last[4] - session_high) / session_high * 20, 0.93
                ),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] London breakup h{curr_hour} RSI={curr_rsi:.0f} vol={vols[-1]/avg_vol:.1f}x",
            )

        # SHORT: price breaks below last 6-bar low during London in downtrend
        session_low = min(c[3] for c in ohlcv[-7:-1])
        breakout_dn = last[4] < session_low and last[3] < session_low

        if (
            breakout_dn
            and vol_surge
            and macro_dn
            and 32 < curr_rsi < 55
            and bearish_bar
            and hist < 0
        ):
            return Signal(
                "short",
                confidence=min(0.82 + (session_low - last[4]) / session_low * 20, 0.93),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] London breakdown h{curr_hour} RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"[{symbol}] h{curr_hour} close={last[4]:.0f} hi6={session_high:.0f}",
        )

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No London session breakout on BTC/ETH/SOL")
