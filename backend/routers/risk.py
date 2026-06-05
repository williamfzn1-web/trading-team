from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db
from services.risk_manager import get_risk_status

router = APIRouter()


@router.get("/status")
def risk_status(db: Session = Depends(get_db)):
    return get_risk_status(db)


@router.post("/reset/{analyst_id}")
def reset_analyst_pause(analyst_id: int, db: Session = Depends(get_db)):
    analyst = db.query(models.Analyst).filter(models.Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail="Analyst not found")
    analyst.paused_until = None
    analyst.pause_reason = None
    analyst.consecutive_losses = 0
    # Force-enable for rest of today so daily loss check can't re-trigger immediately
    analyst.force_trade_until = datetime.utcnow().replace(hour=23, minute=59, second=59)
    db.commit()
    return {"ok": True, "analyst": analyst.name}


@router.post("/toggle/{analyst_id}")
def toggle_analyst_pause(analyst_id: int, db: Session = Depends(get_db)):
    analyst = db.query(models.Analyst).filter(models.Analyst.id == analyst_id).first()
    if not analyst:
        raise HTTPException(status_code=404, detail="Analyst not found")
    now = datetime.utcnow()
    is_paused = analyst.paused_until and analyst.paused_until > now
    if is_paused:
        analyst.paused_until = None
        analyst.pause_reason = None
        analyst.force_trade_until = now.replace(hour=23, minute=59, second=59)
        db.commit()
        return {"ok": True, "action": "resumed", "analyst": analyst.name}
    else:
        analyst.paused_until = datetime(9999, 12, 31)
        analyst.pause_reason = "手動暫停"
        analyst.force_trade_until = None
        db.commit()
        return {"ok": True, "action": "paused", "analyst": analyst.name}
