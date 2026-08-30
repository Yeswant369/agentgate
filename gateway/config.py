from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration. In production every required value must be present at
    boot — a missing secret must crash the deploy, never a live request."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # dev | production
    database_url: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    @model_validator(mode="after")
    def fail_fast_in_production(self) -> "Settings":
        if self.env != "production":
            return self
        missing = [name for name in ("database_url",) if not getattr(self, name)]
        if missing:
            raise ValueError(
                f"ENV=production but required settings are missing: {', '.join(missing)}"
            )
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError(
                "database_url must use the postgresql+psycopg:// scheme "
                "(Neon pooled connection string, psycopg3 driver)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
