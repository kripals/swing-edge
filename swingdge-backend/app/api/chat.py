"""
AI Stock Chat API endpoints.

POST /api/chat/stock  — send a message, get Claude response
GET  /api/chat/history — last 20 messages
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import verify_token
from app.utils.limiter import limiter

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    ticker: str | None = None


class ChatMessageResponse(BaseModel):
    reply: str
    ticker: str | None
    context_used: str


class ChatHistoryItem(BaseModel):
    id: int
    user_message: str
    ai_reply: str
    ticker: str | None
    context_used: str
    created_at: str


@router.post("/stock", dependencies=[Depends(verify_token)])
@limiter.limit("10/minute")
async def chat_stock(
    request: Request,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    from app.services import stock_chat
    from app.config import get_settings

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI chat is not configured — ANTHROPIC_API_KEY missing")

    try:
        result = await stock_chat.chat(db, body.message, ticker=body.ticker)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    return ChatMessageResponse(
        reply=result.reply,
        ticker=result.ticker,
        context_used=result.context_used,
    )


@router.get("/history", dependencies=[Depends(verify_token)])
async def get_chat_history(db: AsyncSession = Depends(get_db)) -> list[ChatHistoryItem]:
    from app.models.chat_history import ChatHistory

    result = await db.execute(
        select(ChatHistory).order_by(desc(ChatHistory.created_at)).limit(20)
    )
    rows = result.scalars().all()

    # Return in chronological order for the chat UI
    return [
        ChatHistoryItem(
            id=r.id,
            user_message=r.user_message,
            ai_reply=r.ai_reply,
            ticker=r.ticker,
            context_used=r.context_used,
            created_at=r.created_at.isoformat(),
        )
        for r in reversed(rows)
    ]
