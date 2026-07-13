"""Housing Estate Application wizard endpoints - the parent object the
whole guided workflow revolves around (see app/applications/service.py and
the approved implementation plan). This slice covers create/get/list and
Step 1's poster attachment + advance; Steps 2-6's dedicated endpoints land
in their own follow-up slices, each validated the same way: every mutating
action re-checks `current_step` server-side (app.applications.steps) so
the wizard can't be forced out of order from the client, and every action
is recorded both in `Application.step_history` and the global audit log.

Read access (Viewer+) is intentionally broader than write access
(Editor+), matching the Poster Archive's existing role split.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.api.schemas import (
    ApplicationAttachPosterRequest,
    ApplicationListResponse,
    ApplicationOut,
)
from app.applications.service import (
    ApplicationNotFoundError,
    attach_poster,
    create_application,
    get_application,
    list_applications,
)
from app.applications.steps import StepTransitionError
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.models import ApplicationStatus, Poster, UserRole

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def start_application(
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.EDITOR)),
):
    application = create_application(db, started_by=user.username)
    db.commit()
    db.refresh(application)
    record_audit(user.username, "application_started", "application", application.id)
    return application


@router.get("", response_model=ApplicationListResponse)
def get_applications(
    status_filter: str | None = Query(default=None, alias="status"),
    mine: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    parsed_status: ApplicationStatus | None = None
    if status_filter:
        try:
            parsed_status = ApplicationStatus(status_filter)
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid status: {status_filter!r}")
    results, total = list_applications(
        db,
        status=parsed_status,
        started_by=user.username if mine else None,
        skip=skip,
        limit=limit,
    )
    return {"total": total, "results": results}


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application_detail(application_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    try:
        return get_application(db, application_id)
    except ApplicationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")


@router.post("/{application_id}/step1/attach-poster", response_model=ApplicationOut)
def attach_poster_to_application(
    application_id: str,
    payload: ApplicationAttachPosterRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.EDITOR)),
):
    try:
        application = get_application(db, application_id)
    except ApplicationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    poster = db.get(Poster, payload.poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster not found")

    try:
        attach_poster(db, application, poster_id=payload.poster_id, actor=user.username)
    except StepTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    db.commit()
    db.refresh(application)
    record_audit(
        user.username,
        "application_poster_attached",
        "application",
        application.id,
        detail={"poster_id": payload.poster_id},
    )
    return application
