"""
Application configuration.

Reads all settings from environment variables (or a .env file in development).
Fails fast on startup if any required value is missing or has the wrong type —
this is intentional so you catch config problems immediately, not mid-request.

Usage:
    from app.config import settings
    print(settings.database_url)
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    development = "development"
    test = "test"
    production = "production"


class StorageBackend(str, Enum):
    local = "local"
    s3 = "s3"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Looks for .env in the directory you run the process from.
        # In Docker this is /app; locally it's backend/.
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",           # silently ignore unknown env vars
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: AppEnv = AppEnv.development
    debug: bool = False
    app_secret_key: str = Field(..., min_length=32)  # HMAC pepper — NIST recommends >=32 bytes

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        ...,
        description=(
            "Async SQLAlchemy URL. "
            "Use postgresql+asyncpg://... for Postgres (local or Neon). "
            "Use sqlite+aiosqlite:///:memory: for tests only."
        ),
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        ...,
        description=(
            "Redis connection URL. "
            "redis://... for local/plain, rediss://... for Upstash TLS."
        ),
    )

    # ── Encryption (BYOK key storage) ─────────────────────────────────────────
    fernet_key: str = Field(
        ...,
        description=(
            "Fernet symmetric encryption key used to encrypt user API keys at rest. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\". "
            "In production, read from AWS Secrets Manager — never commit a real value."
        ),
    )

    # ── JWT auth ──────────────────────────────────────────────────────────────
    jwt_secret: str = Field(..., min_length=32)  # HS256 key — NIST recommends >=32 bytes
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60     # 1 hour — short-lived access tokens

    # ── AWS (only used in production / when storage_backend=s3) ───────────────
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = ""          # empty in local dev — validated below

    # ── OpenRouter ────────────────────────────────────────────────────────────
    openrouter_demo_key: str = ""    # optional, only needed for DEMO_MODE
    demo_mode: bool = False

    # ── Sentry ───────────────────────────────────────────────────────────────────
    sentry_dsn: str = ""   # leave empty to disable

    # ── CORS ─────────────────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:3000"  # comma-separated list

    # ── ECS / Fargate (production only) ──────────────────────────────────────────
    ecs_cluster: str = ""
    ecs_task_definition: str = ""
    ecs_subnet_ids: str = ""
    ecs_security_group_ids: str = ""

    # ── Internal API secret (EventBridge reconciliation) ─────────────────────────
    app_internal_secret: str = ""

        # ── Feature flags ─────────────────────────────────────────────────────────
    storage_backend: StorageBackend = StorageBackend.local

    # ── Derived helpers ───────────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_s3_in_production(self) -> "Settings":
        if self.is_production and self.storage_backend.value == "s3" and not getattr(self, "aws_s3_bucket", ""):
            raise ValueError(
                "AWS_S3_BUCKET must be set when STORAGE_BACKEND=s3 in production"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.production

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.development

    @property
    def is_test(self) -> bool:
        return self.app_env == AppEnv.test

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("aws_s3_bucket")
    @classmethod
    def s3_bucket_required_in_prod(cls, v: str, info: object) -> str:
        """Fail fast if S3 backend is selected but bucket name is missing."""
        # We can't directly access other fields in a field_validator, so this
        # is enforced at the model level via model_validator in production.
        return v

    @field_validator("fernet_key")
    @classmethod
    def fernet_key_must_not_be_placeholder(cls, v: str) -> str:
        bad = {"GENERATE_A_REAL_KEY_DO_NOT_COMMIT", "", "change-me"}
        if v in bad:
            raise ValueError(
                "FERNET_KEY is set to a placeholder. "
                "Generate a real key: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        return v

    @field_validator("redis_url")
    @classmethod
    def redis_url_must_be_tls_in_production(cls, v: str, info) -> str:
        import os
        if os.environ.get("APP_ENV") == "production" and v and not v.startswith("rediss://"):
            raise ValueError("Redis must use TLS (rediss://) in production")
        return v


    @field_validator("app_secret_key")
    @classmethod
    def app_secret_key_must_not_be_placeholder(cls, v: str) -> str:
        import os
        bad = {"GENERATE_A_REAL_SECRET_DO_NOT_COMMIT", "", "change-me", "change-me-in-prod"}
        if os.environ.get("APP_ENV", "development") == "production":
            bad.add("test-secret")
        if v in bad:
            raise ValueError(
                "app_secret_key is a placeholder — set a real 32+ character secret. "
                "Warning: changing this invalidates all stored passwords."
            )
        return v

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_must_not_be_placeholder(cls, v: str) -> str:
        import os
        bad = {"GENERATE_A_REAL_SECRET_DO_NOT_COMMIT", "", "change-me"}
        # Allow "test-secret" only in test/dev environments
        if os.environ.get("APP_ENV", "development") == "production":
            bad.add("test-secret")
        if v in bad:
            raise ValueError(
                "jwt_secret is a placeholder — set a real secret in .env"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using lru_cache means .env is parsed exactly once per process.
    In tests, call get_settings.cache_clear() between test cases if you
    need to swap env vars.
    """
    return Settings()


# Convenient module-level alias — most modules just do `from app.config import settings`
settings = get_settings()
