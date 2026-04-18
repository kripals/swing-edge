from sqlalchemy import Date, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[Date] = mapped_column(Date, unique=True)
    tsx_composite: Mapped[float | None] = mapped_column(Numeric(10, 2))
    sp500: Mapped[float | None] = mapped_column(Numeric(10, 2))
    usd_cad: Mapped[float | None] = mapped_column(Numeric(8, 4))
    boc_rate: Mapped[float | None] = mapped_column(Numeric(4, 2))
    wti_oil: Mapped[float | None] = mapped_column(Numeric(8, 2))
    gold: Mapped[float | None] = mapped_column(Numeric(10, 2))
    nat_gas: Mapped[float | None] = mapped_column(Numeric(8, 4))
    copper: Mapped[float | None] = mapped_column(Numeric(8, 4))
    cpi: Mapped[float | None] = mapped_column(Numeric(4, 2))
    portfolio_value_cad: Mapped[float | None] = mapped_column(Numeric(12, 2))  # total portfolio CAD at close
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SectorPerformance(Base):
    __tablename__ = "sector_performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[Date] = mapped_column(Date)
    sector: Mapped[str] = mapped_column(Numeric(50))                    # "Energy", "Banks", etc.
    etf_ticker: Mapped[str] = mapped_column(Numeric(20))                # XEG.TO, ZEB.TO, etc.
    performance_1d: Mapped[float | None] = mapped_column(Numeric(6, 2))
    performance_5d: Mapped[float | None] = mapped_column(Numeric(6, 2))
    performance_20d: Mapped[float | None] = mapped_column(Numeric(6, 2))
    relative_strength: Mapped[float | None] = mapped_column(Numeric(6, 2))  # vs TSX composite
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(6, 2))       # vs 20-day avg
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
