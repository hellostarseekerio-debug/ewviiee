"""Central application settings.

All runtime configuration is sourced from environment variables / .env so the
same code can run against SQLite or PostgreSQL, and against any supported AI
provider, without code changes.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AIProviderName(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"


class OCREngineName(str, Enum):
    PADDLE = "paddle"
    TESSERACT = "tesseract"


class DatabaseBackend(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OAP_", extra="ignore")

    app_name: str = "Office Automation Platform"
    environment: str = "development"
    data_dir: Path = Path("./data")
    config_dir: Path = Path("./config")

    # Database
    database_backend: DatabaseBackend = DatabaseBackend.SQLITE
    sqlite_path: Path = Path("./data/office_automation.db")
    postgres_dsn: str | None = None

    # AI provider selection - switching this alone changes provider, no code edits
    ai_provider: AIProviderName = AIProviderName.LOCAL
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-06-01"
    local_llm_base_url: str = "http://localhost:11434"
    local_llm_model: str = "llama3"

    # OCR
    ocr_primary_engine: OCREngineName = OCREngineName.PADDLE
    ocr_fallback_engine: OCREngineName = OCREngineName.TESSERACT
    ocr_confidence_threshold: float = 0.75
    ocr_max_retries: int = 2
    ocr_languages: list[str] = Field(default_factory=lambda: ["ch_tra", "ch_sim", "en"])

    # Security
    secret_key: str = Field(default="change-me-in-production")
    encryption_key: str | None = None
    access_token_expire_minutes: int = 60
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8000"])
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = False
    rate_limit_login: str = "5/minute"
    rate_limit_default: str = "120/minute"

    # Set to true only when a reverse proxy (nginx/Caddy) sits directly in
    # front of this app and is the sole way to reach it - otherwise the
    # per-IP rate limiter and account-lockout-adjacent logging would see
    # every request as coming from the proxy's address, making rate
    # limiting a single shared bucket for every user instead of per-client.
    # trusted_proxy_hosts is an exact-match list (or "*" to trust any
    # directly-connecting peer) of addresses allowed to set
    # X-Forwarded-For/X-Forwarded-Proto - "*" is appropriate for the
    # Docker Compose deployment, where the API is already unreachable
    # except via the loopback-published port (see docs/DEPLOYMENT.md).
    trust_proxy_headers: bool = False
    trusted_proxy_hosts: str = "127.0.0.1"

    # File upload safety
    max_upload_size_bytes: int = 25 * 1024 * 1024  # 25 MB
    allowed_upload_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".zip"]
    )

    # Storage roots for import sources
    dropbox_root: Path | None = None
    google_drive_root: Path | None = None
    onedrive_root: Path | None = None
    local_import_root: Path = Path("./data/import")
    archive_root: Path = Path("./data/archive")
    export_root: Path = Path("./data/export")

    # Plugin system
    plugins_dir: Path = Path("./app/plugins")
    enabled_plugins: list[str] = Field(default_factory=lambda: ["housing_estate_poster"])

    # Backups
    backup_dir: Path = Path("./data/backups")
    backup_retention_days: int = 90

    # ZIP export (app/storage/archive_zip.py, POST /api/posters/export/zip).
    # Hard caps so an "export everything" request can't exhaust server
    # memory/disk - a request over either limit is rejected outright
    # (never silently truncated). Requests over zip_export_sync_threshold
    # files are handed to a background ExportJob instead of blocking the
    # HTTP worker for the whole build.
    zip_export_sync_threshold: int = 200
    zip_export_max_files: int = 5000
    zip_export_max_total_bytes: int = 500 * 1024 * 1024  # 500 MB
    export_jobs_dir: Path = Path("./data/export/jobs")

    @property
    def database_url(self) -> str:
        if self.database_backend == DatabaseBackend.POSTGRESQL:
            if not self.postgres_dsn:
                raise ValueError("postgres_dsn must be set when database_backend=postgresql")
            dsn = self.postgres_dsn
            # Some managed-Postgres providers (Render, Heroku-style DSNs)
            # hand out connection strings using the legacy "postgres://"
            # scheme. SQLAlchemy 1.4+ dropped the "postgres" dialect alias,
            # so create_engine() raises NoSuchModuleError on that scheme -
            # normalize it here so the DSN works unmodified regardless of
            # which provider generated it, rather than requiring every
            # caller (build_engine, alembic/env.py) to remember to do so.
            if dsn.startswith("postgres://"):
                dsn = "postgresql://" + dsn[len("postgres://") :]
            return dsn
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.sqlite_path}"

    def assert_secure_for_production(self) -> None:
        """Refuses to start with known-insecure defaults when
        OAP_ENVIRONMENT=production. Called at API/GUI startup."""
        if self.environment != "production":
            return
        if self.secret_key == "change-me-in-production":
            raise RuntimeError(
                "OAP_SECRET_KEY is still the insecure default. Set a unique random "
                "secret (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`) "
                "before running in production."
            )
        if len(self.secret_key) < 32:
            raise RuntimeError(
                "OAP_SECRET_KEY is too short (must be at least 32 characters) - a short or "
                "guessable secret lets an attacker forge JWTs. Generate one with "
                "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`."
            )
        if not self.encryption_key:
            raise RuntimeError(
                "OAP_ENCRYPTION_KEY is not set. Required in production so encrypted "
                "secrets survive restarts - see app.core.security.EncryptionKeyMissingError."
            )
        if "*" in self.cors_allowed_origins:
            raise RuntimeError("OAP_CORS_ALLOWED_ORIGINS must not include '*' in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
