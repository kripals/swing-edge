from sqlalchemy import String, Numeric, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradingRule(Base):
    """
    Database-driven trading rules. Editable via Settings UI without code changes.
    See architecture v3 section 6.2 for the full list of defaults.
    """
    __tablename__ = "trading_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rule_value: Mapped[str] = mapped_column(String(200), nullable=False)   # stored as string, cast at use
    value_type: Mapped[str] = mapped_column(String(20), default="float")   # "float" | "int" | "bool" | "string"
    description: Mapped[str | None] = mapped_column(Text)
    is_editable: Mapped[bool] = mapped_column(Boolean, default=True)       # False = hardcoded safety rule
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
