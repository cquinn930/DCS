"""Application configuration.

Loads settings from environment variables with sensible defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "DCS API"
    app_version: str = "0.2.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://dcs:dcs@localhost:5432/dcs"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://:dcs_redis_dev@localhost:6379/0"

    # Authentication
    jwt_secret_key: str = "CHANGE-THIS-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # OIDC (optional)
    oidc_enabled: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    # Public base URL of *this* API as it appears to the outside world
    # (i.e. how Okta / Azure AD reach the /sso/callback endpoint). Used
    # to auto-fill redirect_uri when a tenant saves OIDC config without
    # one. Override in .env on the deploy host, e.g.
    #   API_PUBLIC_URL=https://falreports.example.com
    api_public_url: str = "http://localhost:8000"

    # Security
    cors_origins: list[str] = ["http://localhost:3000"]
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Audit
    audit_retention_days: int = 2555  # ~7 years

    # Compliance defaults
    default_jurisdiction: str = "NJ"
    default_retention_years: int = 7


    def validate_production_settings(self) -> None:
        """Raise if critical secrets are still at their defaults in production."""
        if self.environment == "production":
            if self.jwt_secret_key == "CHANGE-THIS-IN-PRODUCTION":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong random value in production"
                )
            if self.database_url.endswith("dcs:dcs@localhost:5432/dcs"):
                raise ValueError(
                    "DATABASE_URL must not use default dev credentials in production"
                )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.validate_production_settings()
    return settings
