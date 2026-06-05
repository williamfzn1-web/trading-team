from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Signal:
    action: str  # 'long' | 'short' | 'hold'
    confidence: float = 0.5
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    reason: str = ""


class BaseStrategy:
    name: str = "Base"
    symbols: List[str] = ["BTC/USDT"]
    leverage: int = 2
    max_positions: int = 2
    risk_pct: float = 0.05  # position_size = balance * risk_pct

    def get_signal(self, ohlcv_map: Dict[str, list]) -> Signal:
        raise NotImplementedError

    def should_close(self, trade, current_price: float) -> bool:
        if trade.stop_loss:
            if trade.side == "long" and current_price <= trade.stop_loss:
                return True
            if trade.side == "short" and current_price >= trade.stop_loss:
                return True
        if trade.take_profit:
            if trade.side == "long" and current_price >= trade.take_profit:
                return True
            if trade.side == "short" and current_price <= trade.take_profit:
                return True
        return False
