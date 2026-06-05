from strategies.base import BaseStrategy, Signal
from strategies.indicators import adx, atr, ema, rsi


class MomentumBreakoutStrategy(BaseStrategy):
    """RSI momentum breakout: fires when RSI crosses above 58 (bull) or below 42 (bear).
    Targets momentum SHIFTS rather than price-level breakouts, which are noisy on hourly.
    """

    name = "Momentum Breakout"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 1
    risk_pct = 0.05  # WF -50%, reversal OOS
    bypass_trend_filter = True

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 50:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        rsi_prev = rsi(closes[:-5])  # RSI 5 bars ago
        curr_adx = adx(ohlcv)

        e200 = ema(closes, 200)
        uptrend = curr > e200[-1]

        avg_vol = sum(vols[-20:]) / 20
        vol_conf = vols[-1] > avg_vol * 1.2

        # RSI momentum cross: just entered bull/bear momentum zone
        rsi_bull = curr_rsi > 58 and rsi_prev <= 58
        rsi_bear = curr_rsi < 42 and rsi_prev >= 42

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0

        if rsi_bull and uptrend and vol_conf and curr_adx > 18:
            return Signal(
                "long",
                confidence=0.80,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"RSI cross 58↑ ({rsi_prev:.0f}→{curr_rsi:.0f}) ADX={curr_adx:.0f} vol={vols[-1]/avg_vol:.1f}x",
            )

        if rsi_bear and not uptrend and vol_conf and curr_adx > 18:
            return Signal(
                "short",
                confidence=0.78,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"RSI cross 42↓ ({rsi_prev:.0f}→{curr_rsi:.0f}) ADX={curr_adx:.0f} vol={vols[-1]/avg_vol:.1f}x",
            )

        return Signal(
            "hold",
            reason=f"RSI={curr_rsi:.0f} prev={rsi_prev:.0f} ADX={curr_adx:.0f} uptrend={uptrend}",
        )
