from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(10))
    sector: Mapped[str | None] = mapped_column(String(50))
    added_reason: Mapped[str | None] = mapped_column(Text)              # "Scanner: RSI pullback in uptrend"
    status: Mapped[str] = mapped_column(String(20), default="watching") # watching | entry_ready | entered | expired
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
