from strategies.base import BaseStrategy, Signal
from strategies.indicators import ema, rsi


class ArbitrageStrategy(BaseStrategy):
    """Funding rate proxy + BTC/ETH relative value arbitrage."""

    name = "Arbitrage"
    symbols = ["BTC/USDT", "ETH/USDT"]
    leverage = 1
    max_positions = 2
    risk_pct = 0.40

    def get_signal(self, ohlcv_map: dict) -> Signal:
        btc = ohlcv_map.get("BTC/USDT")
        eth = ohlcv_map.get("ETH/USDT")
        if not btc or not eth or len(btc) < 60:
            return Signal("hold", reason="insufficient data")

        btc_closes = [c[4] for c in btc]
        eth_closes = [c[4] for c in eth]

        # BTC/ETH ratio z-score (50-bar lookback)
        ratios = [b / e for b, e in zip(btc_closes, eth_closes)]
        ratio_mean = sum(ratios[-50:]) / 50
        ratio_std = (sum((r - ratio_mean) ** 2 for r in ratios[-50:]) / 50) ** 0.5
        curr_ratio = ratios[-1]
        ratio_z = (curr_ratio - ratio_mean) / (ratio_std + 1e-9)

        btc_rsi = rsi(btc_closes)
        btc_rsi_prev = rsi(btc_closes[:-3])  # RSI 3 bars ago (more responsive)

        # RSI momentum direction: fading = RSI turning down from peak (reversal signal)
        rsi_fading_from_top = btc_rsi < btc_rsi_prev and btc_rsi > 52
        rsi_fading_from_bottom = btc_rsi > btc_rsi_prev and btc_rsi < 48

        # Ratio also needs to show reversal: current ratio lower than 3 bars ago
        ratio_peak = ratio_z > 1.4 and ratios[-1] < ratios[-3]
        ratio_trough = ratio_z < -1.4 and ratios[-1] > ratios[-3]

        if ratio_peak and rsi_fading_from_top:
            return Signal(
                "short",
                confidence=min(ratio_z / 3.0, 0.85),
                stop_loss_pct=0.025,
                take_profit_pct=0.062,
                reason=f"BTC/ETH ratio z={ratio_z:.2f}Ïƒ fading â€” BTC premium peak. RSI={btc_rsi:.0f}â†“",
            )

        if ratio_trough and rsi_fading_from_bottom:
            return Signal(
                "long",
                confidence=min(abs(ratio_z) / 3.0, 0.85),
                stop_loss_pct=0.025,
                take_profit_pct=0.062,
                reason=f"BTC/ETH ratio z={ratio_z:.2f}Ïƒ recovering â€” BTC discount trough. RSI={btc_rsi:.0f}â†‘",
            )

        return Signal(
            "hold",
            reason=f"Ratio z={ratio_z:.2f}Ïƒ, BTC_RSI={btc_rsi:.0f}, peak={ratio_peak}, trough={ratio_trough}",
        )

