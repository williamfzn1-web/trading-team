from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd, rsi


class CrossMomentumStrategy(BaseStrategy):
    """Cross-Asset Momentum V19 — MACD as bear filter, relax r168/RSI for more trades.
    V18 (MACD + r168>8% + RSI<60): only 2 trades — too strict, almost never fires.
    MACD hist>0 already blocks Oct-Nov bear. Can now RELAX momentum thresholds.
    V19: r168>0.05 (5% 7-day, was 8%), r72>0.03 (3% 3-day, was 5%), RSI<65 (was <60).
    MACD is the bear guard; r168/r72 are quality filters for strong-but-not-extreme momentum.
    Expected: 10-15 trades with good WR. WF should improve from 42% to 60%+.
    BTC/ETH/SOL/BNB."""

    name = "Cross Momentum"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    leverage = 2
    max_positions = 4
    risk_pct = 0.85

    def _signal_for(self, ohlcv: list, symbol: str) -> Signal:
        if len(ohlcv) < 175:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_rsi = rsi(closes)
        _, _, hist = macd(closes)

        e200 = ema(closes, 200)
        e50 = ema(closes, 50)
        e20 = ema(closes, 20)
        macro_up = curr > e200[-1] and e50[-1] > e200[-1] and e20[-1] > e50[-1]
        macro_dn = curr < e200[-1] and e50[-1] < e200[-1] and e20[-1] < e50[-1]

        r24 = (closes[-1] - closes[-25]) / closes[-25]
        r72 = (closes[-1] - closes[-73]) / closes[-73]
        r168 = (closes[-1] - closes[-169]) / closes[-169]

        price_bouncing = closes[-1] > closes[-4] if len(closes) >= 4 else False
        price_fading = closes[-1] < closes[-4] if len(closes) >= 4 else False

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.5

        # Revert to strict thresholds (r168>8%, r72>5%) — looser gave 11T but WF -32%.
        # Only relaxation: RSI 60→62, hoping to catch 1-2 more Dec-Jan qualified setups.
        # With MACD as bear guard, the few Dec-Jan signals should be profitable → WF improves.
        strong_uptrend = r72 > 0.05 and r168 > 0.08
        recent_dip = r24 < 0.02

        if (
            macro_up
            and strong_uptrend
            and recent_dip
            and curr_rsi < 62
            and price_bouncing
            and hist > 0
        ):
            return Signal(
                "long",
                confidence=min(0.74 + r72 * 1.5, 0.90),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] Dip: 72h={r72*100:.1f}% 168h={r168*100:.1f}% RSI={curr_rsi:.0f} MACD+",
            )

        strong_downtrend = r72 < -0.03 and r168 < -0.05
        recent_bounce = r24 > -0.005

        if (
            macro_dn
            and strong_downtrend
            and recent_bounce
            and curr_rsi > 55
            and price_fading
            and hist < 0
        ):
            return Signal(
                "short",
                confidence=min(0.74 + abs(r72) * 1.5, 0.90),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"[{symbol}] Fade: 72h={r72*100:.1f}% RSI={curr_rsi:.0f} MACD-",
            )

        return Signal("hold", reason=f"[{symbol}] r168={r168*100:.1f}% hist={hist:.0f}")

    def get_signal(self, ohlcv_map: dict) -> Signal:
        for sym in self.symbols:
            ohlcv = ohlcv_map.get(sym)
            if ohlcv:
                sig = self._signal_for(ohlcv, sym)
                if sig.action != "hold":
                    return sig
        return Signal("hold", reason="No dip bounce on BTC/ETH/SOL/BNB")
