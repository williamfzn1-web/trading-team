from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, macd


class WhaleHuntingStrategy(BaseStrategy):
    """Whale volume spike + short-term trend confirmation.

    V2: EMA200 macro -> WF ~10%. Too slow on trend reversals.
    V3: CVD + RSI -> 16 trades, counter-productive, return +4.5%.
    V4: EMA50/20 crossover, remove CVD+RSI, dynamic TP 2.5-4x.
        41 trades, WF 1.044 PASS, return +12.9%.
    V4 is best confirmed version: 41 trades, WF 1.044, return +12.9%.
    V4.1 attempt (vol 2.2, close_pos 0.55) added weak signals -> WF -0.175. Reverted.
    Keep V4 params: vol 2.5, close_pos 0.58/0.42, risk_pct 1.20, dynamic TP 2.5-4x.
    """

    name = "Whale Hunting"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 3
    max_positions = 2
    risk_pct = 1.20

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 75:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        curr = closes[-1]
        curr_bar = ohlcv[-1]
        curr_atr = atr(ohlcv)

        _, _, hist = macd(closes)

        # Short-term trend: EMA20/50 crossover
        e50 = ema(closes, 50)
        e20 = ema(closes, 20)
        trend_up = curr > e50[-1] and e20[-1] > e50[-1]
        trend_dn = curr < e50[-1] and e20[-1] < e50[-1]

        # Volume spike: 2.2x 20-bar average
        avg_vol_20 = sum(volumes[-20:]) / 20
        vol_ratio = volumes[-1] / (avg_vol_20 + 1e-9)
        vol_spike = vol_ratio > 2.5  # V4 calibrated value — 2.2 admitted too many weak signals

        bar_range = curr_bar[2] - curr_bar[3]
        close_pos = (curr_bar[4] - curr_bar[3]) / bar_range if bar_range > 0 else 0.5
        strong_bull_close = curr_bar[4] > curr_bar[1] and close_pos > 0.58
        strong_bear_close = curr_bar[4] < curr_bar[1] and close_pos < 0.42

        # Key price level proximity
        level_5k = round(curr / 5000) * 5000
        level_1k = round(curr / 1000) * 1000
        candidate_levels = {
            level_5k - 5000,
            level_5k,
            level_5k + 5000,
            level_1k - 1000,
            level_1k,
            level_1k + 1000,
        }
        near_level = any(
            abs(curr - lvl) / lvl < 0.006 for lvl in candidate_levels if lvl > 0
        )

        avg_atr_20 = (
            sum(
                atr(ohlcv[max(0, i - 14) : i + 1])
                for i in range(len(ohlcv) - 20, len(ohlcv))
            )
            / 20
        )
        atr_expansion = curr_atr > avg_atr_20 * 1.3

        # ETH confluence (1.8x threshold)
        eth_vol_confirm = False
        ohlcv_eth = ohlcv_map.get("ETH/USDT", [])
        if len(ohlcv_eth) >= 20:
            eth_vols = [c[5] for c in ohlcv_eth]
            eth_avg = sum(eth_vols[-20:]) / 20
            eth_vol_confirm = eth_vols[-1] / (eth_avg + 1e-9) > 1.8

        structure_ok = near_level or atr_expansion or eth_vol_confirm

        # Dynamic TP: vol=2.5 -> 2.5x SL, vol=5.0+ -> 4.5x SL
        tp_mult = min(2.5 + (vol_ratio - 2.5) * 0.8, 4.5)
        sl_pct = max(curr_atr * 1.8 / curr, 0.015)
        tp_pct = sl_pct * tp_mult

        if vol_spike and strong_bull_close and structure_ok and trend_up and hist > 0:
            return Signal(
                "long",
                confidence=0.84,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Whale accum vol={vol_ratio:.1f}x tp={tp_mult:.1f}x ETH={eth_vol_confirm}",
            )

        if vol_spike and strong_bear_close and structure_ok and trend_dn and hist < 0:
            return Signal(
                "short",
                confidence=0.82,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Whale distrib vol={vol_ratio:.1f}x tp={tp_mult:.1f}x ETH={eth_vol_confirm}",
            )

        return Signal(
            "hold",
            reason=f"vol={vol_ratio:.1f} pos={close_pos:.0%} trend_up={trend_up}",
        )
