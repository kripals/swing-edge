from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str

    # ── SnapTrade ─────────────────────────────────────────────────────────────
    snaptrade_client_id: str = ""
    snaptrade_consumer_key: str = ""
    snaptrade_user_id: str = ""
    snaptrade_user_secret_encrypted: str = ""

    # ── Market Data APIs ──────────────────────────────────────────────────────
    twelve_data_key: str = ""
    alpha_vantage_key: str = ""
    finnhub_key: str = ""
    fmp_key: str = ""
    marketaux_key: str = ""

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Security ──────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    fernet_encryption_key: str = ""        # AES-256 for SnapTrade secrets
    trigger_secret: str = "change-me-in-production"  # GitHub Actions → Render

    # ── App Settings ──────────────────────────────────────────────────────────
    app_password: str = "change-me"        # Single-user login password
    risk_per_trade_pct: float = 1.0        # 1% of account per trade
    default_currency: str = "CAD"
    fx_fee_pct: float = 1.5                # Wealthsimple FX each way (%)
    earnings_blackout_days: int = 5
    max_active_trades: int = 5
    trade_expiry_days: int = 10
    min_market_cap_cad: float = 2_000_000_000  # $2B CAD

    # ── Market Hours (Eastern Time) ───────────────────────────────────────────
    market_open_et: str = "09:30"
    market_close_et: str = "16:00"

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:5173", "https://swingdge.vercel.app"]

    # ── Environment ───────────────────────────────────────────────────────────
    environment: str = "development"  # "development" | "production"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def fx_round_trip_pct(self) -> float:
        """Total FX cost for a US stock round-trip (buy + sell)."""
        return self.fx_fee_pct * 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
