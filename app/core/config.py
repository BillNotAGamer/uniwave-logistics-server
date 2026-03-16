from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Migration FastAPI"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./app.db"
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "INFO"
    jwt_secret_key: str = "change-this-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str | None = "UniwaveLogistics"
    jwt_audience: str | None = "UniwaveLogisticsClient"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 15
    password_reset_rate_limit_window_minutes: int = 15
    password_reset_rate_limit_max_requests: int = 3
    password_reset_cooldown_seconds: int = 60
    email_verification_token_expire_minutes: int = 1440
    email_verification_rate_limit_window_minutes: int = 15
    email_verification_rate_limit_max_requests: int = 3
    frontend_base_url: str = "http://localhost:3000"
    frontend_reset_password_url: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@example.com"
    smtp_from_name: str = "Migration FastAPI"
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 10
    default_page_size: int = 20
    max_page_size: int = 100
    vehicles_legacy_unbounded: bool = True
    vehicle_pricing_legacy_unbounded: bool = True
    orders_legacy_unbounded: bool = True
    admin_orders_legacy_unbounded: bool = False
    customers_legacy_unbounded: bool = False
    sales_email: str = "sales@uniwave-logistics.com"
    contact_cc_email: str = "rachel.ho@uniwave-logistics.com"
    contact_recipient_email: str = "support@example.com"
    contact_auto_reply_enabled: bool = True
    quote_lead_notification_email: str | None = None
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_folder: str = "blog-thumbnails"
    enable_dev_startup_db_check: bool = True
    dev_startup_require_alembic_version: bool = True
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_display_name: str = "Admin"
    seed_admin_mark_email_verified: bool = True
    resend_api_key: str | None = None
    resend_from_email: str = "Uniwave Logistics <onboarding@resend.dev>"
    resend_base_url: str = "https://api.resend.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @staticmethod
    def _parse_bool_like(value: bool | str | int, *, field_name: str) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"{field_name} must be a boolean value.")

        if isinstance(value, str):
            normalized = value.strip().lower()
            truthy = {"1", "true", "t", "yes", "y", "on", "debug"}
            falsy = {"0", "false", "f", "no", "n", "off", "", "release"}
            if normalized in truthy:
                return True
            if normalized in falsy:
                return False

        raise ValueError(
            f"{field_name} must be a boolean value. "
            "Accepted values: true/false, 1/0, yes/no, on/off, debug/release."
        )

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @field_validator(
        "debug",
        "smtp_use_tls",
        "smtp_use_ssl",
        "contact_auto_reply_enabled",
        "enable_dev_startup_db_check",
        "dev_startup_require_alembic_version",
        "seed_admin_mark_email_verified",
        mode="before",
    )
    @classmethod
    def parse_boolean_flags(cls, value: bool | str | int, info: ValidationInfo) -> bool:
        return cls._parse_bool_like(value, field_name=info.field_name)

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []

        raw_value = value.strip()
        if raw_value.startswith("["):
            parsed = json.loads(raw_value)
            if not isinstance(parsed, list):
                raise ValueError("CORS_ALLOWED_ORIGINS must be a list.")
            return [str(origin).strip() for origin in parsed if str(origin).strip()]

        return [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_runtime_config(self) -> "Settings":
        normalized_environment = self.environment.strip().lower()
        allowed_environments = {"development", "test", "staging", "production"}
        if normalized_environment not in allowed_environments:
            raise ValueError(
                "ENVIRONMENT must be one of: development, test, staging, production."
            )

        if self.smtp_port <= 0 or self.smtp_port > 65535:
            raise ValueError("SMTP_PORT must be a valid TCP port (1-65535).")

        if self.smtp_use_ssl and self.smtp_use_tls:
            raise ValueError("SMTP_USE_SSL and SMTP_USE_TLS cannot both be true.")

        if self.smtp_username and not self.smtp_password:
            raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is set.")

        cloudinary_values = [
            self.cloudinary_cloud_name,
            self.cloudinary_api_key,
            self.cloudinary_api_secret,
        ]
        if any(cloudinary_values) and not all(cloudinary_values):
            raise ValueError(
                "Cloudinary credentials must include CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET together."
            )

        if self.is_production and self.debug:
            raise ValueError("DEBUG must be false when ENVIRONMENT=production.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
