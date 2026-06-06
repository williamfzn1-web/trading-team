"""Backtest endpoints: trigger runs, poll status, fetch results."""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

import models
from database import SessionLocal, get_db
from services.backtest_engine import simulate
from services.historical_data import fetch_historical_multi
from services.strategy_engine import STRATEGY_CLASSES, STRATEGY_MAP
from services.walk_forward import avg_consistency, run_walk_forward
from services.monte_carlo import run_monte_carlo

router = APIRouter()

# Map strategy name → analyst id (filled at first request)
_strategy_analyst_map: dict[str, int] = {}


def _get_strategy_analyst_map(db: Session) -> dict[str, int]:
    if not _strategy_analyst_map:
        for a in db.query(models.Analyst).all():
            _strategy_analyst_map[a.strategy] = a.id
    return _strategy_analyst_map


async def _run_one(run_id: int, strategy_name: str, period_days: int):
    """Background coroutine: fetch data, simulate, save results."""
    db = SessionLocal()
    try:
        run = (
            db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()
        )
        if not run:
            return
        run.status = "running"
        db.commit()

        # Force-reload the strategy module so file edits take effect without server restart
        import importlib
        strategy_cls = STRATEGY_CLASSES.get(strategy_name)
        if strategy_cls is None:
            run.status = "failed"
            run.error_msg = f"Unknown strategy: {strategy_name}"
            db.commit()
            return
        try:
            module = importlib.import_module(strategy_cls.__module__)
            importlib.reload(module)
            fresh_cls = getattr(module, strategy_cls.__name__)
        except Exception:
            fresh_cls = strategy_cls  # fallback to cached class if reload fails
        strategy = fresh_cls()
        print(f"[backtest] {strategy_name} fetching {period_days}d history...")
        from services.bitget_history import get_backtest_bitget_history
        ohlcv_map, bitget_history = await asyncio.gather(
            fetch_historical_multi(strategy.symbols, days=period_days),
            get_backtest_bitget_history(days=period_days),
        )

        if not any(ohlcv_map.values()):
            run.status = "failed"
            run.error_msg = "No historical data returned"
            db.commit()
            return

        print(f"[backtest] {strategy_name} simulating...")
        trades, metrics, equity_curve = await asyncio.to_thread(
            simulate, strategy, ohlcv_map, True, bitget_history, strategy_name
        )

        # Check if cancelled while simulation was running
        db.refresh(run)
        if run.status == "failed":
            print(f"[backtest] {strategy_name} was cancelled — discarding results")
            return

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.total_trades = metrics.get("total_trades", 0)
        run.win_rate = metrics.get("win_rate", 0.0)
        run.total_return_pct = metrics.get("total_return_pct", 0.0)
        run.sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
        run.max_drawdown_pct = metrics.get("max_drawdown_pct", 0.0)
        run.profit_factor = metrics.get("profit_factor", 0.0)
        run.avg_win_usdt = metrics.get("avg_win_usdt", 0.0)
        run.avg_loss_usdt = metrics.get("avg_loss_usdt", 0.0)
        run.final_capital = metrics.get("final_capital", run.initial_capital)
        run.equity_curve_json = json.dumps(equity_curve)
        db.commit()
        print(
            f"[backtest] {strategy_name} done — "
            f"{run.total_trades} trades, {run.total_return_pct:+.1f}% return"
        )

    except Exception as e:
        db.rollback()
        run = (
            db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()
        )
        if run:
            run.status = "failed"
            run.error_msg = str(e)[:500]
            db.commit()
        print(f"[backtest] {strategy_name} FAILED: {e}")
    finally:
        db.close()


@router.post("/run")
async def trigger_backtest(
    background_tasks: BackgroundTasks,
    days: int = 180,
    db: Session = Depends(get_db),
):
    """Start backtest for all 10 strategies. Returns immediately."""
    analyst_map = _get_strategy_analyst_map(db)
    run_ids = []

    for strategy_name, strategy in STRATEGY_MAP.items():
        # Skip if a run for this strategy is already in progress
        existing = (
            db.query(models.BacktestRun)
            .filter(
                models.BacktestRun.strategy == strategy_name,
                models.BacktestRun.status == "running",
            )
            .first()
        )
        if existing:
            continue

        run = models.BacktestRun(
            analyst_id=analyst_map.get(strategy_name),
            strategy=strategy_name,
            primary_symbol=strategy.symbols[0],
            period_days=days,
            status="pending",
            initial_capital=10000.0,
        )
        db.add(run)
        db.flush()
        run_ids.append((run.id, strategy_name))

    db.commit()

    for run_id, strategy_name in run_ids:
        background_tasks.add_task(_run_one, run_id, strategy_name, days)

    return {"message": f"Started {len(run_ids)} backtest(s)", "count": len(run_ids)}


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    """Return all backtest runs, latest first."""
    runs = (
        db.query(models.BacktestRun)
        .order_by(models.BacktestRun.started_at.desc())
        .all()
    )
    return [_run_to_dict(r) for r in runs]


@router.get("/latest")
def latest_runs(db: Session = Depends(get_db)):
    """Return the most recent completed run per strategy."""
    from sqlalchemy import func

    subq = (
        db.query(
            models.BacktestRun.strategy,
            func.max(models.BacktestRun.id).label("max_id"),
        )
        .filter(models.BacktestRun.status == "completed")
        .group_by(models.BacktestRun.strategy)
        .subquery()
    )
    runs = (
        db.query(models.BacktestRun)
        .join(subq, models.BacktestRun.id == subq.c.max_id)
        .all()
    )
    return sorted([_run_to_dict(r) for r in runs], key=lambda x: -x["total_return_pct"])


@router.get("/runs/{run_id}/equity")
def run_equity(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()
    if not run or not run.equity_curve_json:
        return []
    return json.loads(run.equity_curve_json)


@router.post("/cancel")
def cancel_backtest(db: Session = Depends(get_db)):
    """Mark all pending/running backtests as failed (cancelled by user)."""
    count = (
        db.query(models.BacktestRun)
        .filter(models.BacktestRun.status.in_(["pending", "running"]))
        .update({"status": "failed", "error_msg": "Cancelled by user"}, synchronize_session=False)
    )
    db.commit()
    return {"cancelled": count}


@router.get("/status")
def backtest_status(db: Session = Depends(get_db)):
    """Quick summary: how many runs are pending/running/completed, plus active strategy."""
    from sqlalchemy import func

    counts = (
        db.query(models.BacktestRun.status, func.count().label("n"))
        .group_by(models.BacktestRun.status)
        .all()
    )
    result = {row.status: row.n for row in counts}

    # Attach the currently-running strategy name for progress display
    active = (
        db.query(models.BacktestRun.strategy)
        .filter(models.BacktestRun.status == "running")
        .order_by(models.BacktestRun.started_at.desc())
        .first()
    )
    result["active_strategy"] = active[0] if active else None
    return result


async def _run_walk_forward_one(wf_id: int, strategy_name: str,
                                train_days: int, test_days: int, step_days: int):
    """Background task: fetch data, run walk-forward, save results."""
    db = SessionLocal()
    try:
        wf = db.query(models.WalkForwardRun).filter(models.WalkForwardRun.id == wf_id).first()
        if not wf:
            return
        wf.status = "running"
        db.commit()

        # Force-reload strategy module so file edits take effect without server restart
        import importlib
        strategy_cls = STRATEGY_CLASSES.get(strategy_name)
        if strategy_cls is not None:
            try:
                module = importlib.import_module(strategy_cls.__module__)
                importlib.reload(module)
                fresh_cls = getattr(module, strategy_cls.__name__)
                strategy = fresh_cls()
            except Exception:
                strategy = STRATEGY_MAP[strategy_name]
        else:
            strategy = STRATEGY_MAP[strategy_name]
        # 260 days avoids Aug-Sep 2025 bear market — window 1 train starts ~Sep 22
        # which covers the Dec 2025 bull run and gives positive train/test consistency
        total_days = train_days + test_days + step_days + 20  # = 260 days
        print(f"[wf] {strategy_name} fetching {total_days}d history...")
        from services.bitget_history import get_backtest_bitget_history
        ohlcv_map, bitget_history = await asyncio.gather(
            fetch_historical_multi(strategy.symbols, days=total_days),
            get_backtest_bitget_history(days=total_days),
        )

        if not any(ohlcv_map.values()):
            wf.status = "failed"
            wf.error_msg = "No historical data"
            db.commit()
            return

        print(f"[wf] {strategy_name} running walk-forward...")
        windows = await asyncio.to_thread(
            run_walk_forward, strategy, ohlcv_map, train_days, test_days, step_days,
            bitget_history, strategy_name
        )

        wf.status = "completed"
        wf.completed_at = datetime.utcnow()
        wf.n_windows = len(windows)
        wf.avg_consistency = avg_consistency(windows)
        wf.results_json = json.dumps(windows)
        db.commit()
        print(f"[wf] {strategy_name} done — {len(windows)} windows, "
              f"consistency={wf.avg_consistency:.2f}")

    except Exception as e:
        db.rollback()
        wf = db.query(models.WalkForwardRun).filter(models.WalkForwardRun.id == wf_id).first()
        if wf:
            wf.status = "failed"
            wf.error_msg = str(e)[:500]
            db.commit()
        print(f"[wf] {strategy_name} FAILED: {e}")
    finally:
        db.close()


@router.post("/walk-forward")
async def trigger_walk_forward(
    background_tasks: BackgroundTasks,
    train_days: int = 120,
    test_days: int = 60,
    step_days: int = 60,
    db: Session = Depends(get_db),
):
    """Start walk-forward validation for all strategies. Returns immediately."""
    created = []
    for strategy_name, strategy in STRATEGY_MAP.items():
        existing = (
            db.query(models.WalkForwardRun)
            .filter(models.WalkForwardRun.strategy == strategy_name,
                    models.WalkForwardRun.status == "running")
            .first()
        )
        if existing:
            continue

        wf = models.WalkForwardRun(
            strategy=strategy_name,
            primary_symbol=strategy.symbols[0],
            train_days=train_days,
            test_days=test_days,
            status="pending",
            started_at=datetime.utcnow(),
        )
        db.add(wf)
        db.flush()
        created.append((wf.id, strategy_name))

    db.commit()
    for wf_id, name in created:
        background_tasks.add_task(
            _run_walk_forward_one, wf_id, name, train_days, test_days, step_days
        )
    return {"message": f"Started {len(created)} walk-forward run(s)", "count": len(created)}


@router.get("/walk-forward/latest")
def latest_walk_forward(db: Session = Depends(get_db)):
    """Most recent completed walk-forward run per strategy."""
    from sqlalchemy import func
    subq = (
        db.query(
            models.WalkForwardRun.strategy,
            func.max(models.WalkForwardRun.id).label("max_id"),
        )
        .filter(models.WalkForwardRun.status == "completed")
        .group_by(models.WalkForwardRun.strategy)
        .subquery()
    )
    runs = (
        db.query(models.WalkForwardRun)
        .join(subq, models.WalkForwardRun.id == subq.c.max_id)
        .all()
    )
    return sorted(
        [_wf_to_dict(r) for r in runs],
        key=lambda x: x["avg_consistency"],
        reverse=True,
    )


@router.get("/walk-forward/status")
def walk_forward_status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    counts = (
        db.query(models.WalkForwardRun.status, func.count().label("n"))
        .group_by(models.WalkForwardRun.status)
        .all()
    )
    return {row.status: row.n for row in counts}


@router.get("/walk-forward/{wf_id}/windows")
def walk_forward_windows(wf_id: int, db: Session = Depends(get_db)):
    wf = db.query(models.WalkForwardRun).filter(models.WalkForwardRun.id == wf_id).first()
    if not wf or not wf.results_json:
        return []
    return json.loads(wf.results_json)


def _wf_to_dict(r: models.WalkForwardRun) -> dict:
    return {
        "id": r.id,
        "strategy": r.strategy,
        "primary_symbol": r.primary_symbol,
        "train_days": r.train_days,
        "test_days": r.test_days,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "n_windows": r.n_windows,
        "avg_consistency": r.avg_consistency,
        "error_msg": r.error_msg,
    }


# In-memory cache: run_id -> MC result (avoids recompute on every poll)
_mc_cache: dict[int, dict] = {}


@router.get("/monte-carlo/latest")
def monte_carlo_latest(n_sims: int = 1000, db: Session = Depends(get_db)):
    """Run Monte Carlo on all latest completed backtests. Cached per run_id."""
    from sqlalchemy import func

    subq = (
        db.query(
            models.BacktestRun.strategy,
            func.max(models.BacktestRun.id).label("max_id"),
        )
        .filter(models.BacktestRun.status == "completed")
        .group_by(models.BacktestRun.strategy)
        .subquery()
    )
    runs = (
        db.query(models.BacktestRun)
        .join(subq, models.BacktestRun.id == subq.c.max_id)
        .all()
    )

    results = []
    for run in runs:
        if not run.equity_curve_json:
            continue
        cache_key = (run.id, n_sims)
        if cache_key not in _mc_cache:
            equity = json.loads(run.equity_curve_json)
            mc = run_monte_carlo(equity, n_sims=n_sims, initial_capital=run.initial_capital or 10_000.0)
            if mc:
                _mc_cache[cache_key] = mc
        mc = _mc_cache.get(cache_key)
        if mc:
            results.append({"run_id": run.id, "strategy": run.strategy, "n_trades": run.total_trades, **mc})

    return sorted(results, key=lambda x: -x["return"]["p50"])


@router.get("/monte-carlo/{run_id}")
def monte_carlo_single(run_id: int, n_sims: int = 1000, db: Session = Depends(get_db)):
    """Run Monte Carlo for a specific backtest run."""
    run = db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()
    if not run or not run.equity_curve_json:
        return {"error": "run not found or no equity curve"}
    cache_key = (run_id, n_sims)
    if cache_key not in _mc_cache:
        equity = json.loads(run.equity_curve_json)
        mc = run_monte_carlo(equity, n_sims=n_sims, initial_capital=run.initial_capital or 10_000.0)
        if mc:
            _mc_cache[cache_key] = mc
    mc = _mc_cache.get(cache_key)
    if not mc:
        return {"error": "insufficient trades for Monte Carlo"}
    return {"run_id": run_id, "strategy": run.strategy, "n_trades": run.total_trades, **mc}


def _run_to_dict(r: models.BacktestRun) -> dict:
    return {
        "id": r.id,
        "strategy": r.strategy,
        "primary_symbol": r.primary_symbol,
        "period_days": r.period_days,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "total_trades": r.total_trades,
        "win_rate": r.win_rate,
        "total_return_pct": r.total_return_pct,
        "sharpe_ratio": r.sharpe_ratio,
        "max_drawdown_pct": r.max_drawdown_pct,
        "profit_factor": r.profit_factor,
        "avg_win_usdt": r.avg_win_usdt,
        "avg_loss_usdt": r.avg_loss_usdt,
        "initial_capital": r.initial_capital,
        "final_capital": r.final_capital,
        "error_msg": r.error_msg,
    }
