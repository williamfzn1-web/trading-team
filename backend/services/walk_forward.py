"""
Walk-forward validation.

Each run splits historical data into rolling windows:
  - Train window (in-sample):  strategy develops its edge here
  - Test window (out-of-sample): strategy runs on data it never "saw"

A consistent strategy shows similar performance in both periods.
An overfit strategy looks great in-sample but collapses out-of-sample.
"""

from datetime import datetime, timezone

from services.backtest_engine import simulate, WARMUP_BARS


def _ts(candle) -> str:
    return datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d"
    )


def _compact(metrics: dict) -> dict:
    return {
        "return_pct": round(metrics.get("total_return_pct", 0), 2),
        "win_rate": round(metrics.get("win_rate", 0), 1),
        "sharpe": round(metrics.get("sharpe_ratio", 0), 2),
        "max_dd": round(metrics.get("max_drawdown_pct", 0), 2),
        "profit_factor": round(metrics.get("profit_factor", 0), 2),
        "trades": metrics.get("total_trades", 0),
    }


def _consistency(train_ret: float, test_ret: float) -> float:
    """
    How well does out-of-sample mirror in-sample?
      > 0.7  → robust edge
      0.3–0.7 → moderate degradation (normal)
      < 0.3  → likely overfit or unlucky window
      < 0    → complete reversal
    """
    if abs(train_ret) < 0.1:  # near-zero train return → undefined
        return 0.0
    if train_ret > 0:
        return round(min(test_ret / train_ret, 2.0), 3)
    # train was negative
    return round(min(test_ret / abs(train_ret), 2.0) * -1, 3)


def run_walk_forward(
    strategy,
    ohlcv_map: dict,
    train_days: int = 120,
    test_days: int = 60,
    step_days: int = 60,
) -> list[dict]:
    """
    Returns a list of window results. Each entry:
    {
        window, train_start, train_end, test_start, test_end,
        train: {return_pct, win_rate, sharpe, max_dd, profit_factor, trades},
        test:  {return_pct, win_rate, sharpe, max_dd, profit_factor, trades},
        consistency: float   # test_return / train_return
    }
    """
    primary = strategy.symbols[0]
    candles = ohlcv_map.get(primary, [])
    n = len(candles)

    train_bars = train_days * 24  # 1h bars
    test_bars = test_days * 24
    step_bars = step_days * 24

    # Need: warmup + train + test bars minimum
    min_bars = WARMUP_BARS + train_bars + test_bars
    if n < min_bars:
        return []

    windows = []
    window_num = 0
    pos = 0  # start index of current window

    while pos + WARMUP_BARS + train_bars + test_bars <= n:
        window_num += 1

        train_end = pos + WARMUP_BARS + train_bars
        test_end = train_end + test_bars

        # Train slice: pos → train_end
        train_slice = {
            sym: ohlcv_map[sym][pos:train_end]
            for sym in strategy.symbols
            if sym in ohlcv_map
        }

        # Test slice: reuse last WARMUP_BARS of train data as indicator warm-up
        #   then simulate only on the fresh test_bars
        test_slice = {
            sym: ohlcv_map[sym][train_end - WARMUP_BARS : test_end]
            for sym in strategy.symbols
            if sym in ohlcv_map
        }

        train_trades, train_metrics, _ = simulate(strategy, train_slice)
        test_trades, test_metrics, _ = simulate(strategy, test_slice)

        t_ret = train_metrics.get("total_return_pct", 0)
        ts_ret = test_metrics.get("total_return_pct", 0)

        windows.append(
            {
                "window": window_num,
                "train_start": _ts(ohlcv_map[primary][pos + WARMUP_BARS]),
                "train_end": _ts(ohlcv_map[primary][train_end - 1]),
                "test_start": _ts(ohlcv_map[primary][train_end]),
                "test_end": _ts(ohlcv_map[primary][min(test_end - 1, n - 1)]),
                "train": _compact(train_metrics),
                "test": _compact(test_metrics),
                "consistency": _consistency(t_ret, ts_ret),
            }
        )

        pos += step_bars

    return windows


def avg_consistency(windows: list[dict]) -> float:
    if not windows:
        return 0.0
    return round(sum(w["consistency"] for w in windows) / len(windows), 3)
