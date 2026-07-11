"""Regression test for the "type approvalstatus does not exist" failure
seen deploying to Render: alembic/versions/0002 added a column typed
sa.Enum(...) via a bare op.add_column(), which (unlike op.create_table())
never emits the PostgreSQL CREATE TYPE for it - the type only got created
implicitly by op.create_table() in migrations that build a whole table
around an enum column. SQLite has no native enum type (Enum degrades to a
VARCHAR + CHECK constraint there), so this only ever surfaced against a
real PostgreSQL database, never in the SQLite-backed unit/integration
suite.

Skipped unless both psycopg2 is installed AND a real PostgreSQL server is
reachable at OAP_TEST_POSTGRES_DSN (or localhost:5432 with the standard
`postgres`/`postgres` superuser, matching a typical local Postgres
install) - this is the documented optional-Postgres-extra pattern used
elsewhere (see tests/unit/test_database_engine.py), since the plain
`pip install -r requirements.txt && pytest` flow does not include
psycopg2 or a running database.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg2")
import psycopg2  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TEST_DSN = os.environ.get(
    "OAP_TEST_POSTGRES_DSN", "postgresql+psycopg2://postgres:testpass@127.0.0.1:5432/postgres"
)


def _postgres_reachable() -> bool:
    try:
        conn = psycopg2.connect(_TEST_DSN.replace("postgresql+psycopg2://", "postgresql://"))
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=f"No reachable PostgreSQL server at {_TEST_DSN} - set OAP_TEST_POSTGRES_DSN to run this test",
)


@pytest.fixture
def fresh_postgres_db(monkeypatch):
    """Creates a throwaway database on the same server, migrates it, and
    drops it afterward - mirrors a truly fresh Render deploy (no prior
    schema, no prior enum types)."""
    admin_dsn = _TEST_DSN.replace("postgresql+psycopg2://", "postgresql://")
    db_name = "oap_migration_test_tmp"

    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()

    test_dsn = admin_dsn.rsplit("/", 1)[0] + f"/{db_name}"
    monkeypatch.setenv("OAP_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("OAP_POSTGRES_DSN", test_dsn)
    monkeypatch.setenv("OAP_SECRET_KEY", "test-secret-key-for-migration-check-32chars")
    monkeypatch.setenv("OAP_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcy1sb25nISE=")

    from app.core.config import get_settings

    get_settings.cache_clear()

    yield test_dsn

    get_settings.cache_clear()
    conn = psycopg2.connect(admin_dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    conn.close()


def _alembic_config() -> Config:
    cfg = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_REPO_ROOT, "alembic"))
    return cfg


def test_fresh_postgres_database_migrates_to_head(fresh_postgres_db):
    """The exact scenario that failed on Render: a brand-new database,
    migrated from nothing straight to head - must not raise
    psycopg2.errors.UndefinedObject for the approvalstatus enum."""
    command.upgrade(_alembic_config(), "head")


def test_migration_is_safe_to_rerun(fresh_postgres_db):
    """Re-running `alembic upgrade head` against an already-migrated
    database (e.g. a retried deploy) must not error on "type already
    exists"."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")


def test_downgrade_then_upgrade_round_trip(fresh_postgres_db):
    """A full downgrade drops the tables that implicitly created the
    documentstatus/userrole/approvalstatus enum types - downgrade() must
    also drop the types themselves, or the next upgrade fails with
    "type already exists" trying to recreate them."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
