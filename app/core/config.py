from __future__ import annotations

import os
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _nonempty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _normalize_postgres_sqlalchemy_url(url: str) -> str:
    """Railway / Heroku often use postgres://; SQLAlchemy needs postgresql+psycopg2://."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def _postgres_url_from_pg_env() -> str | None:
    """Build DSN from libpq-style vars (common on Railway / managed Postgres)."""
    host = _nonempty(os.environ.get("PGHOST"))
    if not host:
        return None
    port = _nonempty(os.environ.get("PGPORT")) or "5432"
    user = _nonempty(os.environ.get("PGUSER")) or "postgres"
    password = os.environ.get("PGPASSWORD") or ""
    dbname = _nonempty(os.environ.get("PGDATABASE")) or "postgres"
    return (
        "postgresql+psycopg2://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(dbname)}"
    )


def _env_file() -> str | None:
    # On Railway, never load a baked-in .env (it can pin POSTGRES_URL to localhost).
    if any(k.startswith("RAILWAY_") for k in os.environ):
        return None
    return ".env"


def _is_railway_runtime() -> bool:
    return any(k.startswith("RAILWAY_") for k in os.environ)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = "real-time-ml-recommendation-api"
    env: str = "dev"
    postgres_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("POSTGRES_URL", "postgres_url"),
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    database_private_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_PRIVATE_URL", "database_private_url"),
    )
    database_public_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_PUBLIC_URL", "database_public_url"),
    )
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REDIS_URL", "redis_url"),
    )
    redis_ttl_seconds: int = 60 * 60 * 24
    model_path: str = "models/recommender.pkl"
    model_version: str = "v1"
    ab_test_enabled: bool = True
    ab_test_default_bucket: str = "A"
    ab_test_seed: int = 42

    @model_validator(mode="after")
    def _resolve_db_and_redis(self) -> Settings:
        # Prefer DATABASE_* / process env before POSTGRES_URL so a local-style .env
        # (POSTGRES_URL=localhost) cannot override Railway's DATABASE_URL.
        pg = (
            _nonempty(os.environ.get("DATABASE_URL"))
            or _nonempty(os.environ.get("DATABASE_PRIVATE_URL"))
            or _nonempty(os.environ.get("DATABASE_PUBLIC_URL"))
            or _nonempty(os.environ.get("POSTGRES_URL"))
            or _nonempty(self.database_url)
            or _nonempty(self.database_private_url)
            or _nonempty(self.database_public_url)
            or _nonempty(self.postgres_url)
            or _postgres_url_from_pg_env()
        )
        if not pg:
            if _is_railway_runtime():
                raise RuntimeError(
                    "No Postgres URL in this container's environment. On this Railway service open "
                    "Variables, add DATABASE_URL (Reference → Postgres → DATABASE_URL or "
                    "DATABASE_PRIVATE_URL), save, then redeploy. The URL must be defined on the "
                    "service that runs the API container, not only on the Postgres service."
                )
            pg = "postgresql+psycopg2://recommender:recommender@localhost:5432/recommender"
        object.__setattr__(self, "postgres_url", _normalize_postgres_sqlalchemy_url(str(pg)))

        rd = _nonempty(os.environ.get("REDIS_URL")) or _nonempty(self.redis_url)
        if not rd:
            rd = "redis://localhost:6379/0"
        object.__setattr__(self, "redis_url", str(rd))
        return self


settings = Settings()
