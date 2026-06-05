"""Monte Carlo simulation: bootstrap-resample trade returns from equity curve."""

import random
from typing import Optional

import numpy as np

INITIAL_CAPITAL = 10_000.0


def run_monte_carlo(
    equity_curve: list,
    n_sims: int = 1000,
    initial_capital: float = INITIAL_CAPITAL,
) -> Optional[dict]:
    """
    Bootstrap resampling Monte Carlo on equity curve trade returns.

    equity_curve: [[iso_ts, balance], ...] — first point is warmup start,
                  each subsequent point is after a trade closes.

    Returns None if fewer than 3 trades in the curve.
    """
    if len(equity_curve) < 3:
        return None

    balances = [point[1] for point in equity_curve]
    trade_returns = []
    for i in range(1, len(balances)):
        prev = balances[i - 1]
        if prev > 0:
            trade_returns.append((balances[i] - prev) / prev)

    n_trades = len(trade_returns)
    if n_trades < 2:
        return None

    all_final_returns: list[float] = []
    all_max_drawdowns: list[float] = []
    all_curves: list[list[float]] = []

    rng = random.Random()
    for _ in range(n_sims):
        sampled = rng.choices(trade_returns, k=n_trades)
        bal = initial_capital
        peak = bal
        max_dd = 0.0
        path = [bal]
        for r in sampled:
            bal = max(bal * (1.0 + r), 1.0)
            if bal > peak:
                peak = bal
            dd = (peak - bal) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
            path.append(round(bal, 2))

        all_final_returns.append((bal - initial_capital) / initial_capital * 100.0)
        all_max_drawdowns.append(max_dd)
        all_curves.append(path)

    arr = np.array(all_curves, dtype=np.float32)  # (n_sims, n_trades+1)

    # Downsample x-axis to at most 60 points for frontend efficiency
    step = max(1, n_trades // 60)
    indices = list(range(0, n_trades + 1, step))
    if indices[-1] != n_trades:
        indices.append(n_trades)

    sub = arr[:, indices]
    bands = {
        "p5": [round(float(v), 2) for v in np.percentile(sub, 5, axis=0)],
        "p25": [round(float(v), 2) for v in np.percentile(sub, 25, axis=0)],
        "p50": [round(float(v), 2) for v in np.percentile(sub, 50, axis=0)],
        "p75": [round(float(v), 2) for v in np.percentile(sub, 75, axis=0)],
        "p95": [round(float(v), 2) for v in np.percentile(sub, 95, axis=0)],
        "x_labels": indices,
    }

    rets = np.array(all_final_returns, dtype=np.float32)
    dds = np.array(all_max_drawdowns, dtype=np.float32)

    prob_profit = float(np.mean(rets > 0)) * 100.0
    prob_ruin = float(np.mean(rets < -50.0)) * 100.0

    return {
        "n_sims": n_sims,
        "n_trades": n_trades,
        "return": {
            "p5": round(float(np.percentile(rets, 5)), 2),
            "p25": round(float(np.percentile(rets, 25)), 2),
            "p50": round(float(np.percentile(rets, 50)), 2),
            "p75": round(float(np.percentile(rets, 75)), 2),
            "p95": round(float(np.percentile(rets, 95)), 2),
            "mean": round(float(np.mean(rets)), 2),
        },
        "max_drawdown": {
            "p50": round(float(np.percentile(dds, 50)), 2),
            "p95": round(float(np.percentile(dds, 95)), 2),
            "worst": round(float(np.max(dds)), 2),
        },
        "prob_profit_pct": round(prob_profit, 1),
        "prob_ruin_pct": round(prob_ruin, 1),
        "bands": bands,
    }
