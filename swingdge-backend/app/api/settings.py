"""
Settings API endpoints — exposes trading rules for the Settings UI.

GET  /api/settings/rules        — list all trading rules
PATCH /api/settings/rules/:key  — update a single rule value
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.models.trading_rule import TradingRule
from app.services import rules as rules_svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TradingRuleOut(BaseModel):
    id: int
    rule_key: str
    rule_value: str
    value_type: str
    description: str | None
    is_editable: bool
    updated_at: datetime | None

    class Config:
        from_attributes = True


class PatchRuleBody(BaseModel):
    rule_value: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[TradingRuleOut])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Return all trading rules ordered by rule_key."""
    result = await db.execute(select(TradingRule).order_by(TradingRule.rule_key))
    return result.scalars().all()


@router.patch("/rules/{rule_key}", response_model=TradingRuleOut)
async def update_rule(
    rule_key: str,
    body: PatchRuleBody,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_token),
):
    """
    Update a trading rule's value. Only editable rules can be changed.
    Invalidates the in-memory rules cache so the scanner picks up the change immediately.
    """
    result = await db.execute(
        select(TradingRule).where(TradingRule.rule_key == rule_key)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_key}' not found")

    if not row.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Rule '{rule_key}' is a hardcoded safety rule and cannot be changed via API",
        )

    # Validate the new value parses correctly for the rule's type
    try:
        _validate_value(body.rule_value, row.value_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    row.rule_value = body.rule_value
    await db.commit()
    await db.refresh(row)

    # Bust cache so next scanner/trade-plan call sees the new value immediately
    rules_svc.invalidate_cache()

    return row


def _validate_value(raw: str, value_type: str) -> None:
    """Raise ValueError if raw cannot be parsed as value_type."""
    if value_type in ("float", "number", "percentage"):
        float(raw)
    elif value_type in ("int", "integer"):
        int(raw)
    elif value_type in ("bool", "boolean"):
        if raw.lower() not in ("true", "false", "1", "0", "yes", "no"):
            raise ValueError(f"Expected boolean value (true/false), got '{raw}'")
    # string — anything goes
