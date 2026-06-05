from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db

router = APIRouter()


class TradeOpen(BaseModel):
    analyst_id: int
    symbol: str
    side: str  # long / short
    entry_price: float
    quantity: float  # position size in USDT
    leverage: int = 1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = None


class TradeClose(BaseModel):
    exit_price: float


@router.get("/")
def list_trades(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Trade)
    if status:
        q = q.filter(models.Trade.status == status)
    return q.order_by(models.Trade.entry_time.desc()).all()


@router.post("/open")
def open_trade(payload: TradeOpen, db: Session = Depends(get_db)):
    analyst = (
        db.query(models.Analyst).filter(models.Analyst.id == payload.analyst_id).first()
    )
    if not analyst:
        raise HTTPException(status_code=404, detail="Analyst not found")

    margin = payload.quantity / payload.leverage
    if margin > analyst.current_balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    trade = models.Trade(
        analyst_id=payload.analyst_id,
        symbol=payload.symbol,
        side=payload.side,
        entry_price=payload.entry_price,
        quantity=payload.quantity,
        leverage=payload.leverage,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        notes=payload.notes,
        status="open",
    )
    db.add(trade)
    analyst.current_balance -= margin
    db.commit()
    db.refresh(trade)
    return trade


@router.post("/{trade_id}/close")
def close_trade(trade_id: int, payload: TradeClose, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status == "closed":
        raise HTTPException(status_code=400, detail="Trade already closed")

    if trade.side == "long":
        pnl = (
            (payload.exit_price - trade.entry_price)
            / trade.entry_price
            * trade.quantity
        )
    else:
        pnl = (
            (trade.entry_price - payload.exit_price)
            / trade.entry_price
            * trade.quantity
        )

    trade.exit_price = payload.exit_price
    trade.realized_pnl = round(pnl, 2)
    trade.status = "closed"
    trade.exit_time = datetime.utcnow()

    analyst = (
        db.query(models.Analyst).filter(models.Analyst.id == trade.analyst_id).first()
    )
    margin = trade.quantity / trade.leverage
    analyst.current_balance += margin + pnl

    # Snapshot total equity = liquid cash + still-locked margins from other open trades
    remaining_open = (
        db.query(models.Trade)
        .filter(models.Trade.analyst_id == trade.analyst_id, models.Trade.status == "open")
        .all()
    )
    locked_margin = sum(t.quantity / (t.leverage or 1) for t in remaining_open)
    snapshot = models.BalanceSnapshot(
        analyst_id=trade.analyst_id,
        balance=round(analyst.current_balance + locked_margin, 2),
        unrealized_pnl=0.0,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(trade)
    return trade


@router.get("/{trade_id}")
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.Trade).filter(models.Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade
