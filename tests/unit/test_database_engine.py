"""Tests for app.core.database.build_engine's connection-pool configuration.

A PostgreSQL connection dropped by the server (idle timeout, restart,
failover, a NAT in between) must be transparently replaced rather than
surfacing as an OperationalError on whatever request happens to draw it
next - that's what pool_pre_ping/pool_recycle are for. SQLite has no
server-side connection to go stale, so neither applies there.
"""
from __future__ import annotations

import pytest

from app.core.database import build_engine


def test_sqlite_engine_has_no_pool_pre_ping():
    engine = build_engine("sqlite:///:memory:")
    assert engine.pool._pre_ping is False
    engine.dispose()


def test_postgres_style_url_enables_pre_ping_and_recycle():
    # psycopg2 is an optional extra (pip install -e ".[postgres]") not
    # installed by the plain `pip install -r requirements.txt` this test
    # suite otherwise only requires - skip cleanly rather than failing the
    # whole suite for anyone who hasn't installed it, same as the OCR/
    # cloud-AI optional extras elsewhere in this project.
    pytest.importorskip("psycopg2")

    # A real connection is never attempted here - create_engine() is lazy,
    # so this only checks the pool configuration, not connectivity.
    engine = build_engine("postgresql+psycopg2://user:pass@localhost:5432/testdb")
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 1800
    engine.dispose()
