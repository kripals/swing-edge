from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(50))
    # Types: entry_signal | stop_approaching | stop_hit | target_1_hit | target_2_hit
    #        earnings_warning | fx_warning | daily_summary | morning_briefing | scan_complete
    ticker: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10), default="medium") # critical | high | medium | low
    message: Mapped[str] = mapped_column(Text)
    sent_via: Mapped[str | None] = mapped_column(String(20))            # "telegram" | "push" | "both"
    sent_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
