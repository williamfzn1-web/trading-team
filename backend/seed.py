"""Run once to populate the DB with 10 analysts and 18 months of simulated trades."""

import random
from datetime import datetime, timedelta

import numpy as np

import models
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

ANALYSTS = [
    {
        "name": "SMC",
        "strategy": "SMC",
        "color": "#6366F1",
        "description": "Smart Money Concepts — Order Blocks, FVG, BOS/CHOCH",
    },
    {
        "name": "Auction Theory",
        "strategy": "Auction Theory",
        "color": "#8B5CF6",
        "description": "Market Profile POC/VAH/VAL, Value Area breakouts",
    },
    {
        "name": "Order Flow",
        "strategy": "Order Flow",
        "color": "#EC4899",
        "description": "Delta divergence, CVD, bid/ask imbalances",
    },
    {
        "name": "On-chain Data",
        "strategy": "On-chain Data",
        "color": "#F59E0B",
        "description": "Exchange netflow, SOPR, NUPL, Miner Position Index",
    },
    {
        "name": "Arbitrage",
        "strategy": "Arbitrage",
        "color": "#10B981",
        "description": "Funding rate arbitrage, cross-exchange spread capture",
    },
    {
        "name": "Traditional TA",
        "strategy": "Traditional TA",
        "color": "#3B82F6",
        "description": "Multi-timeframe EMA/RSI/MACD confluence signals",
    },
    {
        "name": "Whale Hunting",
        "strategy": "Whale Hunting",
        "color": "#EF4444",
        "description": "Large transfer monitoring, liquidation map analysis",
    },
    {
        "name": "Capital Flow",
        "strategy": "Capital Flow",
        "color": "#14B8A6",
        "description": "Stablecoin mint/burn, BTC ETF flows, DeFi TVL shifts",
    },
    {
        "name": "Liquidity",
        "strategy": "Liquidity",
        "color": "#F97316",
        "description": "Liquidity grabs, stop-hunt reversals, BSL/SSL targeting",
    },
    {
        "name": "Macro/Sentiment",
        "strategy": "Macro/Sentiment",
        "color": "#84CC16",
        "description": "Fear & Greed Index, term structure, macro event calendar",
    },
]

# Realistic recent-ish entry prices for open trades
OPEN_PRICE_RANGES = {
    "BTC/USDT": (64000, 70000),
    "ETH/USDT": (3300, 3700),
    "SOL/USDT": (160, 190),
    "BNB/USDT": (580, 620),
    "AVAX/USDT": (34, 42),
}
SYMBOLS = list(OPEN_PRICE_RANGES.keys())


def _sim_trades(analyst_id: int, initial: float):
    """Return (closed_trades, open_trades, balance_snapshots, final_balance)."""
    win_rate = random.uniform(0.55, 0.72)
    avg_win = random.uniform(0.022, 0.042)
    avg_loss = random.uniform(0.010, 0.020)

    balance = initial
    closed, snapshots = [], []
    current_dt = datetime.utcnow() - timedelta(days=548)  # ~18 months ago

    while current_dt < datetime.utcnow() - timedelta(days=10):
        is_win = random.random() < win_rate
        pnl_pct = (avg_win if is_win else -avg_loss) + random.gauss(0, 0.004)
        qty = balance * random.uniform(0.06, 0.14)
        pnl = qty * pnl_pct
        symbol = random.choice(SYMBOLS)
        side = random.choice(["long", "short"])
        lo, hi = OPEN_PRICE_RANGES[symbol]
        entry = random.uniform(lo * 0.6, hi)  # historical — can be lower
        pct_move = pnl_pct if side == "long" else -pnl_pct
        exit_p = entry * (1 + pct_move)
        duration = timedelta(hours=random.randint(4, 96))

        closed.append(
            {
                "analyst_id": analyst_id,
                "symbol": symbol,
                "side": side,
                "entry_price": round(entry, 4),
                "exit_price": round(exit_p, 4),
                "quantity": round(qty, 2),
                "leverage": random.choice([1, 2, 3, 5]),
                "realized_pnl": round(pnl, 2),
                "status": "closed",
                "entry_time": current_dt,
                "exit_time": current_dt + duration,
            }
        )

        balance = max(balance + pnl, 100.0)
        snapshots.append(
            {
                "analyst_id": analyst_id,
                "balance": round(balance, 2),
                "unrealized_pnl": 0.0,
                "timestamp": current_dt + duration,
            }
        )

        current_dt += duration + timedelta(days=random.randint(1, 4))

    # 1-3 currently open positions with recent prices
    open_trades = []
    for _ in range(random.randint(1, 3)):
        symbol = random.choice(SYMBOLS)
        lo, hi = OPEN_PRICE_RANGES[symbol]
        entry = round(random.uniform(lo, hi), 4)
        qty = round(balance * random.uniform(0.05, 0.10), 2)
        open_trades.append(
            {
                "analyst_id": analyst_id,
                "symbol": symbol,
                "side": random.choice(["long", "short"]),
                "entry_price": entry,
                "exit_price": None,
                "quantity": qty,
                "leverage": random.choice([1, 2, 3]),
                "realized_pnl": 0.0,
                "status": "open",
                "entry_time": datetime.utcnow()
                - timedelta(hours=random.randint(2, 72)),
                "exit_time": None,
            }
        )

    return closed, open_trades, snapshots, balance


def seed():
    db = SessionLocal()
    try:
        if db.query(models.Analyst).count() > 0:
            print("Already seeded — skipping.")
            return

        print("Seeding 10 analysts with 18-month backtest history...\n")
        for meta in ANALYSTS:
            analyst = models.Analyst(
                name=meta["name"],
                strategy=meta["strategy"],
                strategy_description=meta["description"],
                initial_capital=10_000.0,
                current_balance=10_000.0,
                avatar_color=meta["color"],
            )
            db.add(analyst)
            db.flush()

            closed, open_t, snaps, final_bal = _sim_trades(analyst.id, 10_000.0)

            for t in closed + open_t:
                db.add(models.Trade(**t))
            for s in snaps:
                db.add(models.BalanceSnapshot(**s))

            analyst.current_balance = round(final_bal, 2)
            pct = (final_bal - 10_000) / 10_000 * 100
            sign = "+" if pct >= 0 else ""
            print(
                f"  OK  {meta['name']:18s} [{meta['strategy']:15s}]  "
                f"${final_bal:>9,.0f}  ({sign}{pct:.1f}%)"
            )

        db.commit()
        print("\nDatabase seeded successfully!")
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    seed()
