"""Verifies Settings.database_url normalizes the legacy "postgres://" scheme
to "postgresql://". Render's managed PostgreSQL (and other Heroku-style
providers) hand out connection strings using "postgres://", but SQLAlchemy
1.4+ has no "postgres" dialect alias and raises NoSuchModuleError on that
scheme - both `alembic upgrade head` (alembic/env.py) and app.core.database's
build_engine() consume Settings.database_url directly, so without this
normalization the app would fail to start against such a DSN."""
from __future__ import annotations

from app.core.config import DatabaseBackend, Settings


def test_legacy_postgres_scheme_is_normalized_to_postgresql():
    settings = Settings(
        database_backend=DatabaseBackend.POSTGRESQL,
        postgres_dsn="postgres://user:pass@dpg-example-a.oregon-postgres.render.com/office_automation",
    )
    assert settings.database_url.startswith("postgresql://")
    assert settings.database_url == (
        "postgresql://user:pass@dpg-example-a.oregon-postgres.render.com/office_automation"
    )


def test_postgresql_scheme_is_left_unchanged():
    settings = Settings(
        database_backend=DatabaseBackend.POSTGRESQL,
        postgres_dsn="postgresql+psycopg2://user:pass@localhost:5432/testdb",
    )
    assert settings.database_url == "postgresql+psycopg2://user:pass@localhost:5432/testdb"
