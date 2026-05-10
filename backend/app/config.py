import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"change-me", "secret", "password", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60 * 24 * 7

    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session: str = "alerts_session"

    fcm_credentials_file: str | None = None

    rss_poll_seconds: int = 45

    anthropic_api_key: str | None = None  # for AI analysis + Hebrew translation
    finnhub_api_key: str | None = None    # free at finnhub.io

    # Max request body size (bytes) enforced at middleware level
    max_body_size: int = 1 * 1024 * 1024  # 1 MB

    @field_validator("jwt_secret")
    @classmethod
    def _require_strong_secret(cls, v: str) -> str:
        if v.lower() in _INSECURE_SECRETS or len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be set to a random string of at least 32 characters. "
                f"Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("database_url")
    @classmethod
    def _require_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL must be configured in .env")
        return v


settings = Settings()
