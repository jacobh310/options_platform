from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Loaded from environment variables or the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    alpaca_key: str = ""
    alpaca_secret: str = ""
    finnhub_key: str = ""

    # "indicative" works on the free Alpaca plan; "opra" needs a paid plan.
    alpaca_option_feed: str = "indicative"

    database_url: str = f"sqlite:///{(ROOT / 'data' / 'options.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
