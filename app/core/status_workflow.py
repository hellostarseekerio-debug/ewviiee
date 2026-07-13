"""Generic, resource-agnostic status-transition validation.

Deliberately independent of any one model (Poster, Document, ...) so the
same validation shape can be reused wherever a resource gets a real
lifecycle instead of a flat, un-actionable status - see
app/posters/status.py for the first concrete use (Poster Archive) and the
architecture review (docs/ARCHITECTURE_REVIEW_2026-07.md) for why this was
built as a shared service rather than inlined into one route module.
"""
from __future__ import annotations

import enum


class StatusTransitionError(ValueError):
    """Raised when a status change isn't allowed by the resource's
    transition graph. Callers turn this into an HTTP 409 (the state is
    valid, the requested change just isn't permitted from here) - never a
    500, since this is an expected, user-facing outcome of an invalid
    action, not a bug."""


def validate_transition(
    current: enum.Enum,
    new: enum.Enum,
    allowed: dict[enum.Enum, set[enum.Enum]],
    *,
    force: bool = False,
) -> None:
    """Raises StatusTransitionError unless `new` is reachable from `current`
    per `allowed` (or `force` is set, e.g. an admin correcting a mistake).
    Setting the same status again is always a no-op, never an error."""
    if force or new == current:
        return
    permitted = allowed.get(current, set())
    if new not in permitted:
        allowed_names = ", ".join(s.value for s in permitted) or "none"
        raise StatusTransitionError(
            f"Cannot change status from '{current.value}' to '{new.value}' "
            f"(allowed from '{current.value}': {allowed_names})"
        )
