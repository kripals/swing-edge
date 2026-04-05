from sqlalchemy import String, Numeric, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradeHistory(Base):
    __tablename__ = "trade_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_plan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trade_plans.id"))
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    entry_price: Mapped[float] = mapped_column(Numeric(10, 4))
    exit_price: Mapped[float] = mapped_column(Numeric(10, 4))
    shares: Mapped[float] = mapped_column(Numeric(10, 4))
    gross_pnl: Mapped[float] = mapped_column(Numeric(10, 2))
    fx_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    net_pnl: Mapped[float] = mapped_column(Numeric(10, 2))
    hold_days: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(20))                     # "win" | "loss" | "breakeven"
    signal_type: Mapped[str | None] = mapped_column(String(50))
    entered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
