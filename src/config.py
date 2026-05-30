"""Central configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Exchange
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_secret_key: str = Field(default="", alias="BINANCE_SECRET_KEY")
    paper_trading: bool = Field(default=True, alias="PAPER_TRADING")

    # On-chain / market data
    etherscan_api_key: str = Field(default="", alias="ETHERSCAN_API_KEY")
    coinglass_api_key: str = Field(default="", alias="COINGLASS_API_KEY")
    glassnode_api_key: str = Field(default="", alias="GLASSNODE_API_KEY")
    whalealert_api_key: str = Field(default="", alias="WHALEALERT_API_KEY")
    alpha_vantage_api_key: str = Field(default="", alias="ALPHA_VANTAGE_API_KEY")

    # News / sentiment
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")
    cryptopanic_api_key: str = Field(default="", alias="CRYPTOPANIC_API_KEY")
    twitter_bearer_token: str = Field(default="", alias="TWITTER_BEARER_TOKEN")
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(
        default="ETHTradingBot/1.0", alias="REDDIT_USER_AGENT"
    )

    # Alerts
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="ethbot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="ethbot", alias="POSTGRES_USER")
    postgres_password: str = Field(default="changeme", alias="POSTGRES_PASSWORD")
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # Economic calendar
    trading_economics_api_key: str = Field(
        default="", alias="TRADING_ECONOMICS_API_KEY"
    )

    # Bot parameters
    symbol: str = Field(default="ETHUSDT", alias="SYMBOL")
    max_risk_pct: float = Field(default=0.01, alias="MAX_RISK_PCT")
    max_daily_drawdown: float = Field(default=0.03, alias="MAX_DAILY_DRAWDOWN")
    max_total_drawdown: float = Field(default=0.10, alias="MAX_TOTAL_DRAWDOWN")
    max_concurrent_trades: int = Field(default=3, alias="MAX_CONCURRENT_TRADES")
    ml_confidence_threshold: float = Field(
        default=0.72, alias="ML_CONFIDENCE_THRESHOLD"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_async_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
