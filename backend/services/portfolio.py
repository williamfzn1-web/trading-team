import numpy as np


def calculate_win_rate(trades: list) -> float:
    closed = [t for t in trades if t.status == "closed"]
    if not closed:
        return 0.0
    winners = [t for t in closed if t.realized_pnl > 0]
    return round(len(winners) / len(closed) * 100, 1)


def calculate_sharpe_ratio(
    balance_history: list, risk_free_rate: float = 0.05
) -> float:
    if len(balance_history) < 10:
        return 0.0
    snapshots = sorted(balance_history, key=lambda x: x.timestamp)
    balances = [s.balance for s in snapshots]
    returns = np.diff(balances) / np.array(balances[:-1])
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0
    daily_rf = risk_free_rate / 365
    sharpe = (np.mean(returns) - daily_rf) / np.std(returns) * np.sqrt(365)
    return round(float(sharpe), 2)


def calculate_max_drawdown(balance_history: list) -> float:
    if len(balance_history) < 2:
        return 0.0
    snapshots = sorted(balance_history, key=lambda x: x.timestamp)
    balances = [s.balance for s in snapshots]
    peak = balances[0]
    max_dd = 0.0
    for b in balances:
        if b > peak:
            peak = b
        dd = (peak - b) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


def calculate_unrealized_pnl(open_trades: list, current_prices: dict) -> float:
    total = 0.0
    for trade in open_trades:
        base = trade.symbol.split("/")[0]
        price_key = f"{base}/USDT"
        if price_key not in current_prices:
            continue
        current_price = current_prices[price_key]["price"]
        if trade.side == "long":
            pnl = (
                (current_price - trade.entry_price) / trade.entry_price * trade.quantity
            )
        else:
            pnl = (
                (trade.entry_price - current_price) / trade.entry_price * trade.quantity
            )
        total += pnl
    return round(total, 2)


def calculate_occupied_margin(open_trades: list) -> float:
    total = 0.0
    for trade in open_trades:
        lev = trade.leverage if trade.leverage and trade.leverage > 0 else 1
        total += trade.quantity / lev
    return round(total, 2)


def get_account_metrics(
    analyst, trades: list, balance_history: list, current_prices: dict
) -> dict:
    open_trades = [t for t in trades if t.status == "open"]
    closed_trades = [t for t in trades if t.status == "closed"]

    realized_pnl = sum(t.realized_pnl for t in closed_trades)
    unrealized_pnl = calculate_unrealized_pnl(open_trades, current_prices)
    total_pnl = realized_pnl + unrealized_pnl
    pnl_pct = (
        total_pnl / analyst.initial_capital * 100 if analyst.initial_capital > 0 else 0
    )
    occupied_margin = calculate_occupied_margin(open_trades)
    total_equity = round(analyst.current_balance + occupied_margin + unrealized_pnl, 2)

    return {
        "id": analyst.id,
        "name": analyst.name,
        "strategy": analyst.strategy,
        "strategy_description": analyst.strategy_description,
        "avatar_color": analyst.avatar_color,
        "initial_capital": analyst.initial_capital,
        "current_balance": analyst.current_balance,
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": round(total_pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "win_rate": calculate_win_rate(trades),
        "sharpe_ratio": calculate_sharpe_ratio(balance_history),
        "max_drawdown": calculate_max_drawdown(balance_history),
        "total_trades": len(closed_trades),
        "open_positions": len(open_trades),
        "occupied_margin": occupied_margin,
        "total_equity": total_equity,
    }
