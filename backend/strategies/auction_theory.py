from strategies.base import BaseStrategy, Signal
from strategies.indicators import atr, ema, volume_profile


class AuctionTheoryStrategy(BaseStrategy):
    name = "Auction Theory"
    symbols = ["BTC/USDT"]
    leverage = 2
    max_positions = 2
    risk_pct = 0.85

    def get_signal(self, ohlcv_map: dict) -> Signal:
        ohlcv = ohlcv_map.get("BTC/USDT") or ohlcv_map.get(self.symbols[0])
        if not ohlcv or len(ohlcv) < 210:
            return Signal("hold", reason="insufficient data")

        closes = [c[4] for c in ohlcv]
        curr = closes[-1]
        curr_atr = atr(ohlcv)

        # EMA200 trend alignment
        ema200 = ema(closes, 200)
        uptrend = curr > ema200[-1]

        # Volume profile on last 96 candles (4 days — wider context)
        poc, vah, val_ = volume_profile(ohlcv[-96:])

        sl_pct = max(curr_atr * 1.5 / curr, 0.015)
        tp_pct = sl_pct * 3.0  # RR 3:1 → breakeven WR = 25.6%

        # Value buy: price at or below VAL (>0.2%) + uptrend
        if curr < val_ * 0.998 and uptrend:
            dist_pct = (val_ - curr) / val_
            return Signal(
                "long",
                confidence=min(0.60 + dist_pct * 8, 0.88),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Below VAL ${val_:,.0f} by {dist_pct*100:.1f}% in uptrend. POC ${poc:,.0f}",
            )

        # Distribution fade: price at or above VAH (>0.2%) + downtrend
        if curr > vah * 1.002 and not uptrend:
            dist_pct = (curr - vah) / vah
            return Signal(
                "short",
                confidence=min(0.60 + dist_pct * 8, 0.88),
                stop_loss_pct=sl_pct,
                take_profit_pct=tp_pct,
                reason=f"Above VAH ${vah:,.0f} by {dist_pct*100:.1f}% in downtrend. POC ${poc:,.0f}",
            )

        return Signal(
            "hold",
            reason=f"Inside VA [{val_:,.0f}-{vah:,.0f}] or trend mismatch. uptrend={uptrend}",
        )
