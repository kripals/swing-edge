"""
Alerts API endpoints.

GET  /api/alerts       — recent alert history (newest first)
POST /api/alerts/test  — send a test Telegram message + record alert
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.models.alert import Alert
from app.services import telegram as tg

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: int
    type: str
    ticker: str | None
    priority: str
    message: str
    sent_via: str | None
    sent_at: datetime
    acknowledged: bool

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    total: int
    alerts: list[AlertOut]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=AlertListResponse)
async def get_alerts(
    limit: int = Query(default=50, le=200),
    alert_type: str | None = Query(default=None),
    token: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    """Return recent alerts, newest first. Optional filter by type."""
    stmt = select(Alert).order_by(desc(Alert.sent_at)).limit(limit)
    if alert_type:
        stmt = stmt.where(Alert.type == alert_type)

    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return AlertListResponse(total=len(alerts), alerts=list(alerts))


@router.post("/test")
async def send_test_alert(
    token: str = Depends(verify_token),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test message via Telegram and record it."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = (
        f"🔔 <b>SwingEdge Test Alert</b>\n"
        f"If you see this, Telegram notifications are working.\n"
        f"<i>{now}</i>"
    )
    sent = await tg.send_alert(
        db,
        alert_type="scan_complete",
        message=message,
        priority="low",
        skip_cooldown=True,
    )
    return {"sent": sent, "message": message}
