from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db

router = APIRouter()


class MessageCreate(BaseModel):
    analyst_id: int
    content: str
    message_type: Optional[str] = "analysis"


@router.get("/")
def list_messages(limit: int = 100, db: Session = Depends(get_db)):
    msgs = (
        db.query(models.GroupMessage)
        .order_by(models.GroupMessage.timestamp.desc())
        .limit(limit)
        .all()
    )
    # Join analyst name for display
    result = []
    for m in reversed(msgs):
        analyst = (
            db.query(models.Analyst).filter(models.Analyst.id == m.analyst_id).first()
        )
        result.append(
            {
                "id": m.id,
                "analyst_id": m.analyst_id,
                "analyst_name": analyst.name if analyst else "Unknown",
                "analyst_color": analyst.avatar_color if analyst else "#6366F1",
                "strategy": analyst.strategy if analyst else "",
                "content": m.content,
                "message_type": m.message_type,
                "timestamp": m.timestamp.isoformat(),
            }
        )
    return result


@router.post("/")
def post_message(payload: MessageCreate, db: Session = Depends(get_db)):
    msg = models.GroupMessage(
        analyst_id=payload.analyst_id,
        content=payload.content,
        message_type=payload.message_type,
        timestamp=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
