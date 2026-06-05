from strategies.base import BaseStrategy, Signal
from strategies.indicators import adx, atr, ema, rsi


class ADXTrendStrategy(BaseStrategy):
    """ADX-rising entry: fires when ADX crosses above 22 (new trend forming),
    not when ADX has been above 22 for a long time (middle of trend)."""

    name = "ADX Trend"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 1
    risk_pct = 0.05  # backtest -6.4%, WF 30%, both weak
    bypass_trend_filter = True

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 50:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)
        curr_adx = adx(ohlcv)
        prev_adx = adx(ohlcv[:-6])  # ADX 6 bars ago
        curr_rsi = rsi(closes)

        # ADX must be RISING and crossing above 22 — catches trend START, not middle
        adx_rising = curr_adx > prev_adx
        adx_valid = curr_adx > 22

        if not (adx_valid and adx_rising):
            return Signal(
                "hold",
                reason=f"ADX={curr_adx:.1f} prev={prev_adx:.1f} rising={adx_rising}",
            )

        e8 = ema(closes, 8)
        e21 = ema(closes, 21)
        e200 = ema(closes, 200)

        bull = e8[-1] > e21[-1]
        bear = e8[-1] < e21[-1]
        uptrend = curr > e200[-1]

        avg_vol = sum(vols[-20:]) / 20
        vol_conf = vols[-1] > avg_vol * 1.4

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0

        if bull and uptrend and vol_conf and 45 < curr_rsi < 78:
            return Signal(
                "long",
                confidence=0.82,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"ADX rising {prev_adx:.0f}→{curr_adx:.0f} EMA8>21 RSI={curr_rsi:.0f}",
            )

        if bear and not uptrend and vol_conf and 22 < curr_rsi < 55:
            return Signal(
                "short",
                confidence=0.80,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"ADX rising {prev_adx:.0f}→{curr_adx:.0f} EMA8<21 RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"ADX={curr_adx:.1f} bull={bull} uptrend={uptrend} RSI={curr_rsi:.0f}",
        )
