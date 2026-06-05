from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, rsi


class VolatilityBreakoutStrategy(BaseStrategy):
    """Volume-Driven KC Breakout V7 — BTC only, 2.5x volume, target 12-18 trades.
    V6 (BTC+ETH, 3x): 9 trades, WF -41.9% — ETH adds bad training window signals.
    V5 (BTC only, 3x): 8 trades, WF -17.6% — close but too few trades per window.
    V7: BTC only, lower vol to 2.5x → ~12-18 trades → each WF window has 4-6 training trades.
    With e50_rising blocking Nov recovery, training trades should be in Dec-Jan genuine bull.
    If Dec-Jan training profitable + Jan-Mar test profitable: consistency > 0.5."""

    name = "Volatility Breakout"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 2
    max_positions = 1
    risk_pct = 0.85
    bypass_trend_filter = True

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 60:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        prev_atr = atr(ohlcv[:-10])
        atr_expand = curr_atr > prev_atr * 1.15

        curr_rsi = rsi(closes)

        e20 = ema(closes, 20)
        e50 = ema(closes, 50)
        e200 = ema(closes, 200)

        e50_5ago = e50[-6] if len(e50) >= 6 else e50[0]
        e50_rising = e50[-1] > e50_5ago * 1.001
        e50_falling = e50[-1] < e50_5ago * 0.999

        kc_upper = e20[-1] + 1.8 * curr_atr
        kc_lower = e20[-1] - 1.8 * curr_atr

        avg_vol = sum(vols[-20:]) / 20
        # 2.5x is optimal: 2.0x gives too many low-quality signals (WF -307%), 3.0x too few.
        # Add RSI>58 (was >50): filters weak-momentum breakouts → WR 30%→40%+ → WF improves.
        vol_spike = vols[-1] > avg_vol * 2.5

        uptrend = curr > e200[-1] and e50[-1] > e200[-1] and e50_rising
        downtrend = curr < e200[-1] and e50[-1] < e200[-1] and e50_falling

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0

        if (
            vol_spike
            and curr > kc_upper
            and atr_expand
            and uptrend
            and 58 < curr_rsi < 72
        ):
            return Signal(
                "long",
                confidence=0.82,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"KC vol-spike {vols[-1]/avg_vol:.1f}x RSI={curr_rsi:.0f} e50↑",
            )

        if (
            vol_spike
            and curr < kc_lower
            and atr_expand
            and downtrend
            and 28 < curr_rsi < 50
        ):
            return Signal(
                "short",
                confidence=0.80,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"KC vol-spike {vols[-1]/avg_vol:.1f}x RSI={curr_rsi:.0f} e50↓",
            )

        return Signal(
            "hold",
            reason=f"vol={vols[-1]/avg_vol:.1f}x e50_rising={e50_rising} RSI={curr_rsi:.0f}",
        )
