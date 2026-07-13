"""Housing Estate Application wizard: the step<->status mapping and the
allowed step-transition rules.

Steps are linear (1 海報歸檔 -> 2 修改申請信 -> 3 圖片替換 -> 4 AI GENERATION ->
5 QUALITY CHECK -> 6 EXPORT), unlike Poster's branching review graph, so
this is deliberately a simpler shape than app/posters/status.py: advancing
moves exactly one step forward once the current step's work is recorded,
retreating to any earlier step is always allowed (a correction), and
skipping ahead more than one step is never allowed - each step's action
must actually run for its output (parsed poster, edited PDF, replaced
images, generated PDF, QA result) to exist for the next step to use.

A step can independently be marked FAILED from whatever step it failed at;
retrying re-enters that same step's active status without changing
`current_step` - a failure is not itself a step transition.
"""
from __future__ import annotations

from app.core.models import ApplicationStatus

TOTAL_STEPS = 6

STEP_NAMES: dict[int, str] = {
    1: "poster_archive",
    2: "application_letter",
    3: "image_replacement",
    4: "ai_generation",
    5: "quality_check",
    6: "export",
}

# The status an application is in while actively working *on* a given
# step. Step 6 has no distinct "in progress" status of its own - reaching
# it *is* READY (awaiting the user's export actions / "Mark Complete").
STEP_STATUS: dict[int, ApplicationStatus] = {
    1: ApplicationStatus.DRAFT,
    2: ApplicationStatus.EDITING_LETTER,
    3: ApplicationStatus.REPLACING_IMAGES,
    4: ApplicationStatus.GENERATING,
    5: ApplicationStatus.QUALITY_CHECK,
    6: ApplicationStatus.READY,
}


class StepTransitionError(ValueError):
    """Raised when a requested step change isn't allowed from the
    application's current position - callers turn this into an HTTP 409,
    the same convention as app.core.status_workflow.StatusTransitionError."""


def status_for_step(step: int) -> ApplicationStatus:
    try:
        return STEP_STATUS[step]
    except KeyError as exc:
        raise ValueError(f"Not a valid wizard step: {step!r} (expected 1-{TOTAL_STEPS})") from exc


def validate_step_transition(current_step: int, requested_step: int, *, force: bool = False) -> None:
    """Raises StepTransitionError unless `requested_step` is reachable from
    `current_step`: the same step (no-op), any earlier step (a correction),
    or exactly the next step (advancing once the current step's work is
    done). `force` allows an admin to jump arbitrarily, e.g. re-opening a
    stalled application."""
    if force:
        return
    if not (1 <= requested_step <= TOTAL_STEPS):
        raise StepTransitionError(f"Not a valid wizard step: {requested_step} (expected 1-{TOTAL_STEPS})")
    if requested_step <= current_step:
        return
    if requested_step == current_step + 1:
        return
    raise StepTransitionError(
        f"Cannot skip from step {current_step} to step {requested_step} - "
        f"steps must be completed in order (next allowed: {current_step + 1})"
    )


def is_terminal(status: ApplicationStatus) -> bool:
    return status == ApplicationStatus.EXPORTED
