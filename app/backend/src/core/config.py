from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: SecretStr

    # Redis
    REDIS_URL: SecretStr
    CACHE_PREFIX: str = "app_cache"

    # Security
    SECRET_KEY: SecretStr
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_SAMESITE: Literal["lax", "strict", "none"] | None = "lax"
    REFRESH_TOKEN_COOKIE_DOMAIN: str | None = None

    # CORS
    CORS_ORIGINS: str

    # AI Providers
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_WORKERS: int = 1

    # - Development -
    DEV_UVICORN_RELOAD: bool = False

    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
