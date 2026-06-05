"""Shadow vs Live trade comparison endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db

router = APIRouter()


@router.get("/compare")
def compare_trades(db: Session = Depends(get_db)):
    """
    Pair each live trade with its shadow counterpart.
    Returns list of {live, shadow, diff} for closed pairs.
    """
    live_trades = (
        db.query(models.Trade)
        .filter(models.Trade.mode == "live", models.Trade.status == "closed")
        .order_by(models.Trade.exit_time.desc())
        .limit(100)
        .all()
    )
    analyst_map = {a.id: a for a in db.query(models.Analyst).all()}
    result = []

    for lt in live_trades:
        # Find matching shadow trade (same analyst, symbol, side, entry_time)
        st = (
            db.query(models.Trade)
            .filter(
                models.Trade.analyst_id == lt.analyst_id,
                models.Trade.symbol == lt.symbol,
                models.Trade.side == lt.side,
                models.Trade.mode == "shadow",
                models.Trade.entry_time == lt.entry_time,
            )
            .first()
        )

        a = analyst_map.get(lt.analyst_id)
        analyst_name = a.name if a else "?"

        live_row = {
            "id": lt.id,
            "entry_price": lt.entry_price,
            "exit_price": lt.exit_price,
            "realized_pnl": lt.realized_pnl,
        }
        shadow_row = None
        diff = None

        if st:
            shadow_row = {
                "id": st.id,
                "entry_price": st.entry_price,
                "exit_price": st.exit_price,
                "realized_pnl": st.realized_pnl,
            }
            entry_slip = round((lt.entry_price - st.entry_price), 4)
            exit_slip = round(((lt.exit_price or 0) - (st.exit_price or 0)), 4)
            pnl_diff = round(lt.realized_pnl - st.realized_pnl, 2)
            diff = {
                "entry_slippage": entry_slip,
                "exit_slippage": exit_slip,
                "pnl_diff": pnl_diff,
            }

        result.append(
            {
                "analyst": analyst_name,
                "symbol": lt.symbol,
                "side": lt.side,
                "entry_time": lt.entry_time.isoformat() if lt.entry_time else None,
                "exit_time": lt.exit_time.isoformat() if lt.exit_time else None,
                "live": live_row,
                "shadow": shadow_row,
                "diff": diff,
            }
        )

    return result


@router.get("/summary")
def shadow_summary(db: Session = Depends(get_db)):
    """Aggregate slippage and PnL divergence stats."""
    live_closed = (
        db.query(models.Trade)
        .filter(models.Trade.mode == "live", models.Trade.status == "closed")
        .all()
    )
    if not live_closed:
        return {"message": "No live trades yet", "pairs": 0}

    total_pairs = 0
    total_entry_slip = 0.0
    total_exit_slip = 0.0
    total_pnl_diff = 0.0

    for lt in live_closed:
        st = (
            db.query(models.Trade)
            .filter(
                models.Trade.analyst_id == lt.analyst_id,
                models.Trade.symbol == lt.symbol,
                models.Trade.side == lt.side,
                models.Trade.mode == "shadow",
                models.Trade.entry_time == lt.entry_time,
            )
            .first()
        )
        if not st or st.status != "closed":
            continue
        total_pairs += 1
        total_entry_slip += lt.entry_price - st.entry_price
        total_exit_slip += (lt.exit_price or 0) - (st.exit_price or 0)
        total_pnl_diff += lt.realized_pnl - st.realized_pnl

    if total_pairs == 0:
        return {"message": "No matched shadow pairs yet", "pairs": 0}

    return {
        "pairs": total_pairs,
        "avg_entry_slippage": round(total_entry_slip / total_pairs, 4),
        "avg_exit_slippage": round(total_exit_slip / total_pairs, 4),
        "avg_pnl_diff": round(total_pnl_diff / total_pairs, 2),
        "total_pnl_diff": round(total_pnl_diff, 2),
    }
