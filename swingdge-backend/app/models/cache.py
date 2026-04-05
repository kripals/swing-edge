from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    cache_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50))            # "twelve_data" | "finnhub" | "boc" etc.
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
