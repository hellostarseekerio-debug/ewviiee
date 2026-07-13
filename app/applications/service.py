"""Application service: create/attach/advance/retry operations for the
Housing Estate Application wizard, plus the append-only step_history/
ai_logs bookkeeping every one of those operations feeds (see the class
docstring on app.core.models.Application for why this is a standalone
parent object rather than bolted onto Poster or ExportJob).

Every mutating function here takes the already-loaded `Application` row
and the acting user's id/username, appends one entry to `step_history`
(never rewrites a previous entry), and leaves audit-log writing
(app.core.logging_config.record_audit) to the calling route, matching the
convention already used by app/posters/status.py and its callers.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.applications.steps import (
    StepTransitionError,
    status_for_step,
    validate_step_transition,
)
from app.core.models import Application, ApplicationStatus


class ApplicationNotFoundError(ValueError):
    """Raised when an application id doesn't exist - callers turn this
    into an HTTP 404."""


def _append_history(application: Application, *, step: int, status: ApplicationStatus, actor: str | None, detail: str | None) -> None:
    history = list(application.step_history or [])
    history.append(
        {
            "step": step,
            "status": status.value,
            "actor": actor,
            "at": datetime.utcnow().isoformat(),
            "detail": detail,
        }
    )
    application.step_history = history


def append_ai_log(
    application: Application,
    *,
    step: int,
    provider: str,
    operation: str,
    prompt_summary: str | None,
    duration_ms: int | None,
    success: bool,
) -> None:
    """Records one AI call against this application - a per-application
    companion to the global AIUsageLog (app.core.models.AIUsageLog), kept
    here too so one application's complete AI history is visible without
    cross-referencing another table by timestamp/actor."""
    logs = list(application.ai_logs or [])
    logs.append(
        {
            "step": step,
            "provider": provider,
            "operation": operation,
            "prompt_summary": prompt_summary,
            "duration_ms": duration_ms,
            "success": success,
            "at": datetime.utcnow().isoformat(),
        }
    )
    application.ai_logs = logs


def create_application(db: Session, *, started_by: str | None) -> Application:
    """Starts a new application at step 1 (海報歸檔) - the entry point for
    "+ New Application" on the homepage."""
    application = Application(
        status=ApplicationStatus.DRAFT,
        current_step=1,
        started_by=started_by,
        started_at=datetime.utcnow(),
    )
    _append_history(application, step=1, status=ApplicationStatus.DRAFT, actor=started_by, detail="Application started")
    db.add(application)
    db.flush()
    return application


def get_application(db: Session, application_id: str) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise ApplicationNotFoundError(f"No application with id {application_id!r}")
    return application


def attach_poster(db: Session, application: Application, *, poster_id: str, actor: str | None) -> Application:
    """Step 1 output: records the archived Poster this application is for
    and advances to step 2 (修改申請信). Re-attaching a poster while still
    on step 1 is allowed (the user correcting their selection); this never
    moves the application backward."""
    application.poster_id = poster_id
    if application.current_step == 1:
        advance_step(db, application, requested_step=2, actor=actor, detail=f"Poster {poster_id} attached")
    return application


def advance_step(
    db: Session,
    application: Application,
    *,
    requested_step: int,
    actor: str | None,
    detail: str | None = None,
    force: bool = False,
) -> Application:
    """Moves the application to `requested_step`, validating the
    transition (see app.applications.steps.validate_step_transition) and
    recording the new status. A no-op (requested_step == current_step)
    still records a history entry with the given detail, since re-running
    a step's action (e.g. retrying after a correction) is itself worth
    auditing."""
    validate_step_transition(application.current_step, requested_step, force=force)
    application.current_step = requested_step
    new_status = status_for_step(requested_step)
    application.status = new_status
    _append_history(application, step=requested_step, status=new_status, actor=actor, detail=detail)
    return application


def mark_failed(db: Session, application: Application, *, actor: str | None, detail: str | None = None) -> Application:
    """Marks the current step as failed without changing `current_step` -
    a failure is not a step transition, it's an outcome of the step the
    application is already on."""
    application.status = ApplicationStatus.FAILED
    _append_history(application, step=application.current_step, status=ApplicationStatus.FAILED, actor=actor, detail=detail)
    return application


def retry_step(db: Session, application: Application, *, actor: str | None, detail: str | None = None) -> Application:
    """Re-enters the active status for whatever step the application is
    currently on, after a FAILED outcome. Only valid from FAILED - retrying
    a step that hasn't failed is meaningless and almost certainly a bug in
    the caller, so it's rejected rather than silently accepted."""
    if application.status != ApplicationStatus.FAILED:
        raise StepTransitionError("Can only retry an application whose current step has failed")
    new_status = status_for_step(application.current_step)
    application.status = new_status
    _append_history(application, step=application.current_step, status=new_status, actor=actor, detail=detail or "Retrying")
    return application


def complete_application(db: Session, application: Application, *, actor: str | None) -> Application:
    """Step 6's "Mark Complete" - the application's terminal state."""
    if application.current_step != 6:
        raise StepTransitionError("Can only complete an application that has reached step 6 (export)")
    application.status = ApplicationStatus.EXPORTED
    application.completed_by = actor
    application.completed_at = datetime.utcnow()
    _append_history(application, step=6, status=ApplicationStatus.EXPORTED, actor=actor, detail="Marked complete")
    return application


def list_applications(
    db: Session,
    *,
    status: ApplicationStatus | None = None,
    started_by: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Application], int]:
    query = db.query(Application)
    if status is not None:
        query = query.filter(Application.status == status)
    if started_by is not None:
        query = query.filter(Application.started_by == started_by)
    total = query.count()
    results = (
        query.order_by(Application.updated_at.desc()).offset(skip).limit(limit).all()
    )
    return results, total
