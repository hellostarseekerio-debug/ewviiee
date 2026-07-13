"""Covers app/core/status_workflow.py (generic transition validation) and
app/posters/status.py (the Poster Archive's concrete lifecycle rules)."""
from __future__ import annotations

import pytest

from app.core.models import ApprovalStatus, PosterStatus, UserRole
from app.core.status_workflow import StatusTransitionError, validate_transition
from app.posters.status import (
    POSTER_STATUS_TRANSITIONS,
    approval_status_for,
    required_role_for_transition,
    validate_poster_transition,
)


# ---------------------------------------------------------------------------
# Generic engine (app/core/status_workflow.py)
# ---------------------------------------------------------------------------


def test_validate_transition_allows_listed_transition():
    allowed = {PosterStatus.DRAFT: {PosterStatus.PENDING_REVIEW}}
    validate_transition(PosterStatus.DRAFT, PosterStatus.PENDING_REVIEW, allowed)  # no raise


def test_validate_transition_rejects_unlisted_transition():
    allowed = {PosterStatus.DRAFT: {PosterStatus.PENDING_REVIEW}}
    with pytest.raises(StatusTransitionError):
        validate_transition(PosterStatus.DRAFT, PosterStatus.PUBLISHED, allowed)


def test_validate_transition_same_status_is_always_a_noop():
    allowed = {PosterStatus.DRAFT: set()}  # no transitions allowed at all
    validate_transition(PosterStatus.DRAFT, PosterStatus.DRAFT, allowed)  # no raise


def test_validate_transition_force_bypasses_the_graph():
    allowed = {PosterStatus.DRAFT: set()}
    validate_transition(PosterStatus.DRAFT, PosterStatus.ARCHIVED, allowed, force=True)  # no raise


def test_validate_transition_error_message_lists_allowed_targets():
    allowed = {PosterStatus.PENDING_REVIEW: {PosterStatus.APPROVED, PosterStatus.REJECTED}}
    with pytest.raises(StatusTransitionError) as exc_info:
        validate_transition(PosterStatus.PENDING_REVIEW, PosterStatus.PUBLISHED, allowed)
    message = str(exc_info.value)
    assert "pending_review" in message
    assert "published" in message
    assert "approved" in message and "rejected" in message


# ---------------------------------------------------------------------------
# Poster Archive lifecycle (app/posters/status.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,new",
    [
        (PosterStatus.DRAFT, PosterStatus.PENDING_REVIEW),
        (PosterStatus.PENDING_REVIEW, PosterStatus.APPROVED),
        (PosterStatus.PENDING_REVIEW, PosterStatus.REJECTED),
        (PosterStatus.PENDING_REVIEW, PosterStatus.DRAFT),
        (PosterStatus.APPROVED, PosterStatus.PUBLISHED),
        (PosterStatus.APPROVED, PosterStatus.PENDING_REVIEW),
        (PosterStatus.PUBLISHED, PosterStatus.ARCHIVED),
        (PosterStatus.REJECTED, PosterStatus.DRAFT),
        (PosterStatus.REJECTED, PosterStatus.PENDING_REVIEW),
    ],
)
def test_valid_poster_transitions_do_not_raise(current, new):
    validate_poster_transition(current, new)


@pytest.mark.parametrize(
    "current,new",
    [
        (PosterStatus.DRAFT, PosterStatus.APPROVED),
        (PosterStatus.DRAFT, PosterStatus.PUBLISHED),
        (PosterStatus.DRAFT, PosterStatus.ARCHIVED),
        (PosterStatus.PENDING_REVIEW, PosterStatus.PUBLISHED),
        (PosterStatus.PENDING_REVIEW, PosterStatus.ARCHIVED),
        (PosterStatus.APPROVED, PosterStatus.DRAFT),
        (PosterStatus.APPROVED, PosterStatus.ARCHIVED),
        (PosterStatus.PUBLISHED, PosterStatus.DRAFT),
        (PosterStatus.PUBLISHED, PosterStatus.PENDING_REVIEW),
        (PosterStatus.ARCHIVED, PosterStatus.DRAFT),
        (PosterStatus.ARCHIVED, PosterStatus.PUBLISHED),
        (PosterStatus.REJECTED, PosterStatus.APPROVED),
        (PosterStatus.REJECTED, PosterStatus.PUBLISHED),
    ],
)
def test_invalid_poster_transitions_raise(current, new):
    with pytest.raises(StatusTransitionError):
        validate_poster_transition(current, new)


def test_archived_is_terminal_with_no_outgoing_transitions():
    assert POSTER_STATUS_TRANSITIONS[PosterStatus.ARCHIVED] == set()


def test_force_bypasses_poster_transition_graph():
    validate_poster_transition(PosterStatus.ARCHIVED, PosterStatus.DRAFT, force=True)  # no raise


def test_setting_the_same_status_again_is_a_noop_for_every_status():
    for s in PosterStatus:
        validate_poster_transition(s, s)  # must never raise


@pytest.mark.parametrize(
    "target,expected_role",
    [
        (PosterStatus.APPROVED, UserRole.REVIEWER),
        (PosterStatus.REJECTED, UserRole.REVIEWER),
        (PosterStatus.DRAFT, UserRole.EDITOR),
        (PosterStatus.PENDING_REVIEW, UserRole.EDITOR),
        (PosterStatus.PUBLISHED, UserRole.EDITOR),
        (PosterStatus.ARCHIVED, UserRole.EDITOR),
    ],
)
def test_required_role_for_transition(target, expected_role):
    assert required_role_for_transition(target) == expected_role


@pytest.mark.parametrize(
    "status,expected",
    [
        (PosterStatus.DRAFT, ApprovalStatus.PENDING),
        (PosterStatus.PENDING_REVIEW, ApprovalStatus.PENDING),
        (PosterStatus.APPROVED, ApprovalStatus.APPROVED),
        (PosterStatus.PUBLISHED, ApprovalStatus.APPROVED),
        (PosterStatus.ARCHIVED, ApprovalStatus.APPROVED),
        (PosterStatus.REJECTED, ApprovalStatus.REJECTED),
    ],
)
def test_approval_status_for_every_poster_status(status, expected):
    assert approval_status_for(status) == expected


def test_every_poster_status_has_a_transitions_entry():
    """Guards against a future new PosterStatus member being added to the
    enum but forgotten in the transition map (silently making it a dead
    end no one meant to be terminal)."""
    for s in PosterStatus:
        assert s in POSTER_STATUS_TRANSITIONS
