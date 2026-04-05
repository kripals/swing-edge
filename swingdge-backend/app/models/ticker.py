from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Ticker(Base):
    """Master list of tickers the scanner watches."""
    __tablename__ = "ticker_universe"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(10))                   # "TSX" | "NYSE" | "NASDAQ"
    name: Mapped[str | None] = mapped_column(String(200))
    sector: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    is_etf: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)      # False = skip in scanner
    twelve_data_symbol: Mapped[str | None] = mapped_column(String(30))  # e.g. "SU:TSX" or "SU.TO"
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
