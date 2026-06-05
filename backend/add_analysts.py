"""
Add 5 new analysts to an existing database without touching existing data.
Safe to run multiple times — skips analysts that already exist by name.
"""

import random
from datetime import datetime, timedelta

import models
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

NEW_ANALYSTS = [
    {
        "name": "Momentum Breakout",
        "strategy": "Momentum Breakout",
        "color": "#F59E0B",
        "description": "20-bar high/low breakout with ATR expansion and volume confirmation",
    },
    {
        "name": "Mean Reversion",
        "strategy": "Mean Reversion",
        "color": "#06B6D4",
        "description": "Bollinger Band extreme touch + RSI reversal for mean-reversion entries",
    },
    {
        "name": "Volatility Breakout",
        "strategy": "Volatility Breakout",
        "color": "#A855F7",
        "description": "Keltner Channel squeeze-then-breakout, captures volatility expansion",
    },
    {
        "name": "ADX Trend",
        "strategy": "ADX Trend",
        "color": "#22C55E",
        "description": "EMA13/34 crossover pullback entries, only when ADX confirms real trend",
    },
    {
        "name": "Order Book Imbalance",
        "strategy": "Order Book Imbalance",
        "color": "#F43F5E",
        "description": "Net volume delta proxy — sustained buying/selling pressure with trend filter",
    },
    {
        "name": "ICT Fair Value Gap",
        "strategy": "ICT Fair Value Gap",
        "color": "#34D399",
        "description": "ICT Fair Value Gaps — institutional imbalance zones that price revisits to fill orders",
    },
    {
        "name": "Wyckoff Spring",
        "strategy": "Wyckoff Spring",
        "color": "#3B82F6",
        "description": "Wyckoff Spring/Upthrust — false breakouts at accumulation/distribution extremes",
    },
    {
        "name": "VWAP Reversion",
        "strategy": "VWAP Reversion",
        "color": "#8B5CF6",
        "description": "VWAP deviation mean reversion — fade 2-sigma extremes as institutions rebalance",
    },
    {
        "name": "BB Squeeze",
        "strategy": "BB Squeeze",
        "color": "#F97316",
        "description": "Bollinger Band squeeze breakout — explosive moves following low-volatility compression",
    },
    {
        "name": "SuperTrend",
        "strategy": "SuperTrend",
        "color": "#14B8A6",
        "description": "SuperTrend trend-following — ATR-based dynamic support/resistance flip signals",
    },
    {
        "name": "RSI Divergence",
        "strategy": "RSI Divergence",
        "color": "#EF4444",
        "description": "RSI hidden divergence — trend continuation signals via price/momentum divergence",
    },
    {
        "name": "London Breakout",
        "strategy": "London Breakout",
        "color": "#EAB308",
        "description": "London/NY killzone breakout — Asian session range breaks at institutional open hours",
    },
    {
        "name": "Cross Momentum",
        "strategy": "Cross Momentum",
        "color": "#06B6D4",
        "description": "Cross-asset momentum rotation — AQR factor momentum across BTC/ETH/SOL/BNB",
    },
]

OPEN_PRICE_RANGES = {
    "BTC/USDT": (64000, 70000),
    "ETH/USDT": (3300, 3700),
    "SOL/USDT": (160, 190),
    "BNB/USDT": (580, 620),
    "AVAX/USDT": (34, 42),
}
SYMBOLS = list(OPEN_PRICE_RANGES.keys())


def _sim_trades(analyst_id: int, initial: float):
    win_rate = random.uniform(0.52, 0.70)
    avg_win = random.uniform(0.020, 0.040)
    avg_loss = random.uniform(0.010, 0.018)

    balance = initial
    closed, snapshots = [], []
    current_dt = datetime.utcnow() - timedelta(days=365)

    while current_dt < datetime.utcnow() - timedelta(days=10):
        is_win = random.random() < win_rate
        pnl_pct = (avg_win if is_win else -avg_loss) + random.gauss(0, 0.004)
        qty = balance * random.uniform(0.06, 0.14)
        pnl = qty * pnl_pct
        symbol = random.choice(SYMBOLS)
        side = random.choice(["long", "short"])
        lo, hi = OPEN_PRICE_RANGES[symbol]
        entry = random.uniform(lo * 0.7, hi)
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
                "leverage": random.choice([1, 2, 3]),
                "realized_pnl": round(pnl, 2),
                "status": "closed",
                "entry_time": current_dt,
                "exit_time": current_dt + duration,
                "mode": "paper",
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

    return closed, snapshots, balance


def add_analysts():
    db = SessionLocal()
    try:
        existing = {a.name for a in db.query(models.Analyst).all()}
        added = 0

        for meta in NEW_ANALYSTS:
            if meta["name"] in existing:
                print(f"  SKIP {meta['name']} (already exists)")
                continue

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

            closed, snaps, final_bal = _sim_trades(analyst.id, 10_000.0)
            for t in closed:
                db.add(models.Trade(**t))
            for s in snaps:
                db.add(models.BalanceSnapshot(**s))

            analyst.current_balance = round(final_bal, 2)
            pct = (final_bal - 10_000) / 10_000 * 100
            sign = "+" if pct >= 0 else ""
            print(
                f"  ADD  {meta['name']:18s} [{meta['strategy']:22s}]  "
                f"${final_bal:>9,.0f}  ({sign}{pct:.1f}%)"
            )
            added += 1

        db.commit()
        print(f"\nDone — {added} analyst(s) added.")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    add_analysts()
