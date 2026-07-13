"""Unit tests for the Housing Estate Application wizard's step-transition
rules (app/applications/steps.py) - the same "server is the real
authority" validation used by app/posters/status.py, but for a linear
6-step wizard instead of a branching review graph."""
from __future__ import annotations

import pytest

from app.applications.steps import (
    StepTransitionError,
    TOTAL_STEPS,
    status_for_step,
    validate_step_transition,
)
from app.core.models import ApplicationStatus


def test_status_for_step_covers_every_step():
    for step in range(1, TOTAL_STEPS + 1):
        assert isinstance(status_for_step(step), ApplicationStatus)


def test_status_for_step_rejects_out_of_range():
    with pytest.raises(ValueError):
        status_for_step(0)
    with pytest.raises(ValueError):
        status_for_step(7)


def test_advancing_exactly_one_step_is_allowed():
    validate_step_transition(1, 2)
    validate_step_transition(5, 6)


def test_same_step_is_a_noop():
    validate_step_transition(3, 3)


def test_retreating_to_any_earlier_step_is_allowed():
    validate_step_transition(6, 1)
    validate_step_transition(4, 2)


def test_skipping_ahead_is_rejected():
    with pytest.raises(StepTransitionError):
        validate_step_transition(1, 3)
    with pytest.raises(StepTransitionError):
        validate_step_transition(2, 6)


def test_out_of_range_requested_step_is_rejected():
    with pytest.raises(StepTransitionError):
        validate_step_transition(1, 0)
    with pytest.raises(StepTransitionError):
        validate_step_transition(1, 7)


def test_force_allows_any_jump():
    validate_step_transition(1, 6, force=True)
    validate_step_transition(6, 1, force=True)
