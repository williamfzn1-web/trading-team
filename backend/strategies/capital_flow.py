from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, rsi


class CapitalFlowStrategy(BaseStrategy):
    """Track capital rotation: BTC dominance, stablecoin flows, altcoin risk-on/off."""

    name = "Capital Flow"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    def get_signal(self, ohlcv_map: dict) -> Signal:
        btc = ohlcv_map.get("BTC/USDT")
        eth = ohlcv_map.get("ETH/USDT")
        sol = ohlcv_map.get("SOL/USDT")
        if not btc or not eth or len(btc) < 60:
            return Signal("hold", reason="insufficient data")

        btc_closes = [c[4] for c in btc]
        eth_closes = [c[4] for c in eth]
        curr_btc = btc_closes[-1]

        e50_btc = ema(btc_closes, 50)
        e100_btc = ema(btc_closes, 100)
        btc_macro_bull = e50_btc[-1] > e100_btc[-1] and curr_btc > e50_btc[-1]
        btc_macro_bear = e50_btc[-1] < e100_btc[-1] and curr_btc < e50_btc[-1]

        btc_ret_30 = (btc_closes[-1] - btc_closes[-30]) / btc_closes[-30]
        eth_ret_30 = (eth_closes[-1] - eth_closes[-30]) / eth_closes[-30]
        dominance_shift = btc_ret_30 - eth_ret_30

        sol_eth_strength = 0.0
        if sol and len(sol) >= 30:
            sol_closes = [c[4] for c in sol]
            sol_ret = (sol_closes[-1] - sol_closes[-30]) / sol_closes[-30]
            sol_eth_strength = sol_ret - eth_ret_30

        risk_off = dominance_shift > 0.04
        risk_on = dominance_shift < -0.04 and sol_eth_strength > 0.02

        btc_vols = [c[5] for c in btc]
        avg_vol = sum(btc_vols[-20:]) / 20
        true_lull = all(btc_vols[-(i + 2)] < avg_vol * 0.68 for i in range(3))
        vol_surge = btc_vols[-1] > avg_vol * 2.0

        curr_rsi = rsi(btc_closes)
        rsi_3ago = rsi(btc_closes[:-3])
        curr_atr = atr(btc)
        sl_pct = max(curr_atr * 2.0 / curr_btc, 0.02)
        tp_pct = sl_pct * 2.2

        if risk_off and btc_macro_bull and curr_rsi < 58 and curr_rsi > rsi_3ago:
            return Signal(
                "long",
                confidence=0.74,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Capital to BTC: dom={dominance_shift:+.1%}, RSI={curr_rsi:.0f}",
            )

        if true_lull and vol_surge and btc_macro_bull and curr_rsi < 65:
            return Signal(
                "long",
                confidence=0.70,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Dry-powder ignition: vol x{btc_vols[-1]/avg_vol:.1f} after lull",
            )

        if risk_on and btc_macro_bear and curr_rsi > 55 and curr_rsi < rsi_3ago:
            return Signal(
                "short",
                confidence=0.65,
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Risk-on, BTC lagging: dom={dominance_shift:+.1%}, RSI={curr_rsi:.0f}",
            )

        return Signal(
            "hold",
            reason=f"dom={dominance_shift:+.1%}, risk_on={risk_on}, macro_bull={btc_macro_bull}",
        )
