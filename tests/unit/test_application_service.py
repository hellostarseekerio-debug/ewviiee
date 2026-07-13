"""Covers app/applications/service.py's create/attach/advance/retry/
complete operations, against an in-memory SQLite database with the real
ORM models - same convention as tests/unit/test_folder_service.py."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.applications.service import (
    attach_poster,
    complete_application,
    create_application,
    mark_failed,
    retry_step,
)
from app.applications.steps import StepTransitionError
from app.core.models import ApplicationStatus, Base, Poster


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_poster(db) -> Poster:
    poster = Poster(poster_title="Test poster", dropbox_url="https://www.dropbox.com/s/x/f.pdf")
    db.add(poster)
    db.flush()
    return poster


def test_create_application_starts_at_step_one(db):
    app_ = create_application(db, started_by="alice")
    assert app_.current_step == 1
    assert app_.status == ApplicationStatus.DRAFT
    assert app_.started_by == "alice"
    assert len(app_.step_history) == 1
    assert app_.step_history[0]["step"] == 1


def test_attach_poster_advances_to_step_two(db):
    app_ = create_application(db, started_by="alice")
    poster = _make_poster(db)

    attach_poster(db, app_, poster_id=poster.id, actor="alice")

    assert app_.poster_id == poster.id
    assert app_.current_step == 2
    assert app_.status == ApplicationStatus.EDITING_LETTER
    assert len(app_.step_history) == 2


def test_reattaching_poster_while_still_on_step_one_does_not_double_advance(db):
    app_ = create_application(db, started_by="alice")
    poster_a = _make_poster(db)
    poster_b = Poster(poster_title="Other", dropbox_url="https://www.dropbox.com/s/y/f.pdf")
    db.add(poster_b)
    db.flush()

    attach_poster(db, app_, poster_id=poster_a.id, actor="alice")
    assert app_.current_step == 2

    # Already past step 1 - attaching again just updates poster_id, no
    # further auto-advance (current_step stays 2).
    attach_poster(db, app_, poster_id=poster_b.id, actor="alice")
    assert app_.poster_id == poster_b.id
    assert app_.current_step == 2


def test_mark_failed_then_retry_returns_to_the_same_step(db):
    app_ = create_application(db, started_by="alice")
    poster = _make_poster(db)
    attach_poster(db, app_, poster_id=poster.id, actor="alice")
    assert app_.current_step == 2

    mark_failed(db, app_, actor="alice", detail="AI provider timed out")
    assert app_.status == ApplicationStatus.FAILED
    assert app_.current_step == 2  # failure doesn't change position

    retry_step(db, app_, actor="alice")
    assert app_.status == ApplicationStatus.EDITING_LETTER
    assert app_.current_step == 2


def test_retry_without_a_failure_is_rejected(db):
    app_ = create_application(db, started_by="alice")
    with pytest.raises(StepTransitionError):
        retry_step(db, app_, actor="alice")


def test_complete_requires_step_six(db):
    app_ = create_application(db, started_by="alice")
    with pytest.raises(StepTransitionError):
        complete_application(db, app_, actor="alice")


def test_complete_application_sets_terminal_state(db):
    app_ = create_application(db, started_by="alice")
    app_.current_step = 6
    complete_application(db, app_, actor="bob")
    assert app_.status == ApplicationStatus.EXPORTED
    assert app_.completed_by == "bob"
    assert app_.completed_at is not None
