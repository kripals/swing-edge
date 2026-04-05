from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(10))                   # "TSX" | "NYSE" | "NASDAQ"
    shares: Mapped[float] = mapped_column(Numeric(10, 4))
    avg_cost: Mapped[float] = mapped_column(Numeric(10, 4))
    currency: Mapped[str] = mapped_column(String(3))                    # "CAD" | "USD"
    current_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(10, 2))
    unrealized_pnl_pct: Mapped[float | None] = mapped_column(Numeric(6, 2))
    sector: Mapped[str | None] = mapped_column(String(50))
    is_leveraged_etf: Mapped[bool] = mapped_column(Boolean, default=False)
    has_fx_cost: Mapped[bool] = mapped_column(Boolean, default=False)   # True for US stocks without USD account
    added_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
