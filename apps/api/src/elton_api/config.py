"""Runtime configuration for the reviewed local foundation mode."""

from typing import Literal
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ELTON_", extra="forbid", hide_input_in_errors=True,
    )

    mode: Literal["foundation_demo"] = "foundation_demo"
    database_url: SecretStr
    guest_origins: tuple[str, ...]
    admin_origins: tuple[str, ...]
    session_csrf_key: SecretStr
    # Reviewed technical demo values, never a production retention promise.
    guest_session_ttl_seconds: int = Field(default=7 * 24 * 60 * 60, gt=0)
    draft_quote_ttl_seconds: int = Field(default=15 * 60, gt=0)
    guest_creation_limit_per_minute: int = Field(default=30, gt=0)
    admin_login_limit_per_minute: int = Field(default=10, gt=0, le=100)
    admin_session_ttl_seconds: int = Field(default=8 * 60 * 60, gt=0, le=7 * 24 * 60 * 60)
    media_storage_root: Path = Field(default=Path("var/media"))
    ffmpeg_binary: str = Field(default="ffmpeg", min_length=1)
    ffprobe_binary: str = Field(default="ffprobe", min_length=1)
    video_processing_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("A PostgreSQL psycopg URL is required") from None
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError("A PostgreSQL psycopg URL with a database is required")
        return value

    @field_validator("guest_origins")
    @classmethod
    def require_guest_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != ("http://localhost:3000",):
            raise ValueError("The reviewed local guest origin is required")
        return value

    @field_validator("admin_origins")
    @classmethod
    def require_admin_origins(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != ("http://localhost:3001",):
            raise ValueError("The reviewed local admin origin is required")
        return value

    @field_validator("session_csrf_key")
    @classmethod
    def require_csrf_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("A runtime session CSRF key is required")
        return value
