"""SQLAlchemy engine/session management."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class Base:
    """Declarative base marker, real base lives in models.py to avoid circular imports."""


def build_engine(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    # pool_pre_ping issues a cheap "is this connection still alive" check
    # before handing a pooled connection to a request; without it, a
    # connection dropped by PostgreSQL (idle timeout, a DB restart/
    # failover, a NAT/firewall between the app and a managed DB) surfaces
    # as an OperationalError on whatever request happens to draw it next,
    # rather than transparently reconnecting. pool_recycle proactively
    # retires connections older than 30 minutes for the same reason.
    # Neither applies to SQLite (no server-side connection to go stale).
    pool_kwargs = {} if url.startswith("sqlite") else {"pool_pre_ping": True, "pool_recycle": 1800}
    return create_engine(url, connect_args=connect_args, future=True, **pool_kwargs)


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def reset_engine() -> None:
    """Disposes the cached engine/session factory so the next call to
    `get_engine()`/`get_session_factory()` rebuilds from the current
    Settings. Without this, changing `OAP_SQLITE_PATH` (or any other
    database setting) at runtime - e.g. between test cases, or via a
    config reload - would silently keep talking to the old database."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope for a series of operations."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. For production use, prefer Alembic migrations."""
    from app.core.models import Base as ModelsBase

    ModelsBase.metadata.create_all(bind=get_engine())
