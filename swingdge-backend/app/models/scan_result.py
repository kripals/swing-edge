from sqlalchemy import String, Numeric, Boolean, Date, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ScanResult(Base):
    """One row per ticker per scan run that passed all filters."""
    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_date: Mapped[Date] = mapped_column(Date, nullable=False)

    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10))
    current_price: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Signal
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)   # RSI_PULLBACK etc.
    signal_strength: Mapped[float | None] = mapped_column(Numeric(4, 2))   # 0.0–1.0

    # Key indicator snapshot at scan time
    rsi_14: Mapped[float | None] = mapped_column(Numeric(6, 2))
    macd_histogram: Mapped[float | None] = mapped_column(Numeric(10, 4))
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(6, 2))
    above_sma_50: Mapped[bool | None] = mapped_column(Boolean)
    atr_14: Mapped[float | None] = mapped_column(Numeric(10, 4))
    relative_strength: Mapped[float | None] = mapped_column(Numeric(8, 2))

    sector: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    has_trade_plan: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
