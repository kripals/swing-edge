from sqlalchemy import String, Boolean, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))                      # "Kripal TFSA"
    broker: Mapped[str] = mapped_column(String(50), default="wealthsimple")
    account_type: Mapped[str] = mapped_column(String(20))               # "TFSA"
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    has_usd_account: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float | None] = mapped_column(Numeric(12, 2))
    contribution_room: Mapped[float | None] = mapped_column(Numeric(12, 2))
    snaptrade_account_id: Mapped[str | None] = mapped_column(String(100))  # SnapTrade brokerage_authorization id
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
