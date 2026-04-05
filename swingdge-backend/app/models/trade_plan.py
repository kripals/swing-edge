from sqlalchemy import String, Numeric, Date, Integer, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3))
    sector: Mapped[str | None] = mapped_column(String(50))

    # Price levels
    current_price: Mapped[float] = mapped_column(Numeric(10, 4))
    entry_low: Mapped[float] = mapped_column(Numeric(10, 4))
    entry_high: Mapped[float] = mapped_column(Numeric(10, 4))
    stop_loss: Mapped[float] = mapped_column(Numeric(10, 4))
    target_1: Mapped[float] = mapped_column(Numeric(10, 4))
    target_2: Mapped[float] = mapped_column(Numeric(10, 4))

    # Risk / sizing
    risk_reward_ratio: Mapped[float] = mapped_column(Numeric(4, 2))
    position_size_dollars: Mapped[float] = mapped_column(Numeric(10, 2))
    position_size_shares: Mapped[float] = mapped_column(Numeric(10, 4))
    risk_amount: Mapped[float] = mapped_column(Numeric(10, 2))          # 1% of account

    # FX
    fx_cost_pct: Mapped[float] = mapped_column(Numeric(4, 2), default=0.0)
    net_gain_after_fx: Mapped[float | None] = mapped_column(Numeric(6, 2))

    # Earnings
    earnings_date: Mapped[Date | None] = mapped_column(Date)
    earnings_days_away: Mapped[int | None] = mapped_column(Integer)

    # Signal
    signal_type: Mapped[str | None] = mapped_column(String(50))        # "RSI_PULLBACK", "MACD_CROSSOVER"
    signal_score: Mapped[float | None] = mapped_column(Numeric(4, 2))  # 0-100 composite score

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending | active | hit_t1 | hit_t2 | stopped | expired
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    closed_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    actual_pnl: Mapped[float | None] = mapped_column(Numeric(10, 2))
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
