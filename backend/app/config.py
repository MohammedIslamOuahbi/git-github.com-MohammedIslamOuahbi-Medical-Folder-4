from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Medical Clinic Management System"
    app_env: str = "production"
    database_url: str = ""
    pg_dump_path: str | None = None
    pg_restore_path: str | None = None
    postgres_backup_timeout_seconds: int = 600
    postgres_restore_validation_timeout_seconds: int = 120
    postgres_restore_timeout_seconds: int = 1800
    postgres_alembic_timeout_seconds: int = 600
    api_base_url: str = "http://localhost:8000/api/v1"
    secret_key: str = "change-this-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    backend_cors_origins_raw: str = Field(
        default="tauri://localhost,http://tauri.localhost,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000",
        alias="BACKEND_CORS_ORIGINS",
    )

    @model_validator(mode="after")
    def validate_postgresql_database_url(self) -> "Settings":
        if not self.database_url:
            raise ValueError("DATABASE_URL is required and must point to PostgreSQL.")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
            raise ValueError("PostgreSQL is the only supported runtime database. Set DATABASE_URL to postgresql+psycopg://...")
        return self

    @computed_field
    @property
    def backend_cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins_raw.split(",") if origin.strip()]

    @computed_field
    @property
    def backend_cors_origin_regex(self) -> str:
        return (
            r"^(tauri://localhost|https?://tauri\.localhost|https?://"
            r"(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)"
            r"(:\d+)?)$"
        )

    @property
    def is_postgresql(self) -> bool:
        return self.database_url.startswith("postgresql")

    @computed_field
    @property
    def database_backend(self) -> str:
        return "postgresql"

    @computed_field
    @property
    def database_backend_label(self) -> str:
        return "PostgreSQL"

    @computed_field
    @property
    def database_name(self) -> str:
        url = make_url(self.database_url)
        return url.database or "unknown"

    @computed_field
    @property
    def database_host(self) -> str:
        return make_url(self.database_url).host or "unknown"

    @computed_field
    @property
    def database_port(self) -> int:
        return make_url(self.database_url).port or 5432

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
