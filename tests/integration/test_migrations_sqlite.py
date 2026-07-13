"""SQLite-backed Alembic migration tests that always run (no external
Postgres server required, unlike tests/integration/test_postgres_migrations.py
which specifically guards the Postgres-only enum-type pitfall). These cover
the ordinary, always-available case: a fresh SQLite database migrates
cleanly to head, downgrades cleanly back to base, and the schema Phase 2's
folder/export-job/starred-item tables actually need is present and usable
after migrating.

Note: alembic/env.py always resolves its own connection URL from
`get_settings().database_url`, ignoring any `sqlalchemy.url` set on the
Config object passed to `command.upgrade`/`command.downgrade` - so
isolation here comes from the repo's existing autouse `_isolated_settings`
fixture (tests/conftest.py), which points `OAP_SQLITE_PATH` at a fresh
`tmp_path` for every test, not from constructing our own Config URL.
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import get_settings

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _alembic_config() -> Config:
    cfg = Config(os.path.join(_REPO_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_REPO_ROOT, "alembic"))
    return cfg


def _current_db_path():
    return get_settings().sqlite_path


def test_fresh_sqlite_database_migrates_to_head():
    command.upgrade(_alembic_config(), "head")
    assert _current_db_path().exists()


def test_migration_is_safe_to_rerun_on_sqlite():
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # must not error on a retried/duplicate run


def test_downgrade_then_upgrade_round_trip_on_sqlite():
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_head_schema_has_folders_posters_folder_id_and_export_jobs():
    command.upgrade(_alembic_config(), "head")

    engine = sa.create_engine(f"sqlite:///{_current_db_path()}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "folders" in tables
    assert "starred_items" in tables
    assert "export_jobs" in tables
    assert "poster_link_history" in tables

    poster_columns = {c["name"] for c in inspector.get_columns("posters")}
    assert "folder_id" in poster_columns
    assert "status" in poster_columns  # Phase 1's column, still present
    assert "campaign_name" in poster_columns
    assert "government_department" in poster_columns
    assert "version" in poster_columns
    assert "source" in poster_columns
    assert "needs_review" in poster_columns
    assert "dropbox_link_broken" in poster_columns
    assert "dropbox_last_verified_at" in poster_columns


def test_downgrading_to_0006_removes_folder_support_cleanly():
    """Downgrading from head to 0006 must cleanly remove folders/
    starred_items/export_jobs, posters.folder_id, and 0008's extended
    metadata columns, leaving 0006's schema (Phase 1's status column)
    intact. Targets "0006" explicitly (not "-1") so this keeps checking
    the same thing as new migrations are appended after 0008."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006")

    engine = sa.create_engine(f"sqlite:///{_current_db_path()}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "folders" not in tables
    assert "export_jobs" not in tables
    assert "poster_link_history" not in tables

    poster_columns = {c["name"] for c in inspector.get_columns("posters")}
    assert "folder_id" not in poster_columns
    assert "campaign_name" not in poster_columns
    assert "needs_review" not in poster_columns
    assert "status" in poster_columns


def test_downgrading_one_step_from_head_removes_extended_metadata():
    """Downgrading from head by one revision (0008 -> 0007) must cleanly
    remove the extended-metadata columns and poster_link_history, leaving
    folders/status intact."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")

    engine = sa.create_engine(f"sqlite:///{_current_db_path()}")
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    assert "folders" in tables
    assert "poster_link_history" not in tables

    poster_columns = {c["name"] for c in inspector.get_columns("posters")}
    assert "folder_id" in poster_columns
    assert "campaign_name" not in poster_columns
    assert "needs_review" not in poster_columns


def test_migrated_database_can_store_a_folder_and_a_filed_poster():
    """End-to-end sanity check beyond schema shape: actually insert through
    the migrated schema, not just introspect it."""
    command.upgrade(_alembic_config(), "head")

    engine = sa.create_engine(f"sqlite:///{_current_db_path()}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO folders (id, name, parent_id, path, depth, created_at, updated_at) "
                "VALUES ('f1', 'Poster Archive', NULL, 'f1', 0, :now, :now)"
            ),
            {"now": "2026-07-13 00:00:00"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO posters (id, poster_title, dropbox_url, folder_id, approval_status, status, "
                "created_at, updated_at) "
                "VALUES ('p1', 'Test', 'https://www.dropbox.com/x', 'f1', 'PENDING', 'PENDING_REVIEW', :now, :now)"
            ),
            {"now": "2026-07-13 00:00:00"},
        )
        row = conn.execute(sa.text("SELECT folder_id FROM posters WHERE id = 'p1'")).fetchone()
        assert row[0] == "f1"
