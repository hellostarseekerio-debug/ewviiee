"""Poster Archive endpoints - paste-text Dropbox link management.

Security: import/create/edit require Editor+, delete requires Admin+ (same
role thresholds used for the Documents resource). Every mutating action is
recorded in the audit log, matching the rest of the API.
"""
# Deliberately no `from __future__ import annotations` here: every route
# below decorated with `@limiter.limit(...)` is wrapped by slowapi before
# FastAPI ever sees it, and FastAPI resolves PEP 563 deferred string
# annotations using the *decorated* function's `__globals__` - slowapi's
# own module, not this one. See app/api/routes/auth.py's matching comment
# for the full mechanism (this crashed startup under the pinned
# fastapi==0.111.0 the first time this pattern was used unguarded).

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_rule_engine, require_role
from app.api.rate_limit import limiter
from app.api.schemas import (
    PosterBulkDeleteRequest,
    PosterCreateRequest,
    PosterImportRequest,
    PosterImportResponse,
    PosterImportResult,
    PosterListResponse,
    PosterOut,
    PosterUpdateRequest,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.models import Poster, UserRole
from app.posters.parser import parse_poster_text
from app.posters.validation import InvalidDropboxUrlError, assert_valid_dropbox_url
from app.rules.engine import RuleEngine

router = APIRouter(prefix="/api/posters", tags=["posters"])


@router.post("/import", response_model=PosterImportResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_default)
def import_posters(
    request: Request,
    payload: PosterImportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
    rule_engine: RuleEngine = Depends(get_rule_engine),
):
    """Parses a large pasted block of text into one or more poster records
    (see app/posters/parser.py) and bulk-inserts every valid, non-duplicate
    one in a single transaction - efficient for pastes of hundreds/
    thousands of records, and safe to re-paste the same text twice (every
    repeat is reported back as a duplicate, not an error)."""
    parsed_records = parse_poster_text(payload.text, rule_engine)

    results: list[PosterImportResult] = []
    to_insert: list[Poster] = []
    seen_in_batch: set[str] = set()

    urls_in_batch = [p.dropbox_url for p in parsed_records]
    existing_urls: set[str] = set()
    if urls_in_batch:
        existing_urls = {
            row[0]
            for row in db.query(Poster.dropbox_url).filter(Poster.dropbox_url.in_(urls_in_batch)).all()
        }

    for parsed in parsed_records:
        try:
            assert_valid_dropbox_url(parsed.dropbox_url)
        except InvalidDropboxUrlError as exc:
            results.append(
                PosterImportResult(dropbox_url=parsed.dropbox_url, status="invalid_url", reason=str(exc))
            )
            continue

        if parsed.dropbox_url in existing_urls or parsed.dropbox_url in seen_in_batch:
            results.append(PosterImportResult(dropbox_url=parsed.dropbox_url, status="duplicate"))
            continue

        seen_in_batch.add(parsed.dropbox_url)
        poster = Poster(
            district=parsed.district,
            estate=parsed.estate,
            poster_title=parsed.poster_title,
            poster_type=parsed.poster_type,
            route_number=parsed.route_number,
            document_date=parsed.document_date,
            dropbox_url=parsed.dropbox_url,
            language=parsed.language,
            keywords=parsed.keywords or None,
            source_text=parsed.source_text,
        )
        to_insert.append(poster)
        results.append(PosterImportResult(dropbox_url=parsed.dropbox_url, status="imported"))

    if to_insert:
        db.add_all(to_insert)
        db.commit()
        for poster, result in zip(to_insert, [r for r in results if r.status == "imported"]):
            result.id = poster.id

    record_audit(
        actor=current_user.username,
        action="poster_import",
        detail={
            "total_parsed": len(parsed_records),
            "imported": len(to_insert),
            "duplicates": sum(1 for r in results if r.status == "duplicate"),
            "invalid": sum(1 for r in results if r.status == "invalid_url"),
        },
    )

    return PosterImportResponse(
        total_parsed=len(parsed_records),
        imported=len(to_insert),
        duplicates=sum(1 for r in results if r.status == "duplicate"),
        invalid=sum(1 for r in results if r.status == "invalid_url"),
        results=results,
    )


def _apply_filters(
    query,
    district: str | None,
    poster_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    has_dropbox: bool | None,
):
    if district:
        query = query.filter(Poster.district.ilike(f"%{district}%"))
    if poster_type:
        query = query.filter(Poster.poster_type == poster_type)
    if date_from:
        query = query.filter(Poster.document_date >= date_from)
    if date_to:
        query = query.filter(Poster.document_date <= date_to)
    if has_dropbox is True:
        query = query.filter(Poster.dropbox_url.isnot(None))
    elif has_dropbox is False:
        query = query.filter(Poster.dropbox_url.is_(None))
    return query


@router.get("/search", response_model=PosterListResponse)
def search_posters(
    q: str | None = Query(default=None, description="Free-text search across title/district/estate/route/keywords/dropbox URL"),
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(Poster)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Poster.poster_title.ilike(like),
                Poster.district.ilike(like),
                Poster.estate.ilike(like),
                Poster.route_number.ilike(like),
                Poster.dropbox_url.ilike(like),
                Poster.notes.ilike(like),
            )
        )
    query = _apply_filters(query, district, poster_type, date_from, date_to, has_dropbox)
    total = query.count()
    results = query.order_by(Poster.created_at.desc()).offset(skip).limit(limit).all()
    return PosterListResponse(total=total, results=results)


@router.get("/export")
def export_posters_csv(
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = _apply_filters(db.query(Poster), district, poster_type, date_from, date_to, has_dropbox)
    rows = query.order_by(Poster.created_at.desc()).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id", "district", "estate", "poster_title", "poster_type", "route_number",
            "document_date", "dropbox_url", "language", "keywords", "notes",
            "approval_status", "created_at", "updated_at",
        ]
    )
    for poster in rows:
        writer.writerow(
            [
                poster.id,
                poster.district or "",
                poster.estate or "",
                poster.poster_title or "",
                poster.poster_type or "",
                poster.route_number or "",
                poster.document_date.isoformat() if poster.document_date else "",
                poster.dropbox_url or "",
                poster.language or "",
                ", ".join(poster.keywords or []),
                poster.notes or "",
                poster.approval_status.value if hasattr(poster.approval_status, "value") else poster.approval_status,
                poster.created_at.isoformat(),
                poster.updated_at.isoformat(),
            ]
        )

    record_audit(actor=current_user.username, action="poster_export_csv", detail={"row_count": len(rows)})

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=posters_export.csv"},
    )


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_posters(
    payload: PosterBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    deleted = db.query(Poster).filter(Poster.id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    record_audit(
        actor=current_user.username, action="poster_bulk_deleted",
        detail={"requested": len(payload.ids), "deleted": deleted},
    )
    return {"deleted": deleted}


@router.get("", response_model=PosterListResponse)
def list_posters(
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|document_date|district|poster_title)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = _apply_filters(db.query(Poster), district, poster_type, date_from, date_to, has_dropbox)
    total = query.count()
    sort_column = getattr(Poster, sort_by)
    sort_column = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    results = query.order_by(sort_column).offset(skip).limit(limit).all()
    return PosterListResponse(total=total, results=results)


@router.get("/{poster_id}", response_model=PosterOut)
def get_poster(poster_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")
    return poster


@router.post("", response_model=PosterOut, status_code=status.HTTP_201_CREATED)
def create_poster(
    payload: PosterCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    if payload.dropbox_url:
        existing = db.query(Poster).filter(Poster.dropbox_url == payload.dropbox_url).first()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "A poster record with this Dropbox URL already exists")

    poster = Poster(**payload.model_dump(exclude={"workflow_steps"}))
    if payload.workflow_steps is not None:
        poster.workflow_steps = [step.model_dump() for step in payload.workflow_steps]
    db.add(poster)
    db.commit()
    record_audit(
        actor=current_user.username, action="poster_created",
        resource_type="poster", resource_id=poster.id,
    )
    return poster


@router.patch("/{poster_id}", response_model=PosterOut)
def update_poster(
    poster_id: str,
    payload: PosterUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")

    updates = payload.model_dump(exclude_unset=True, exclude={"workflow_steps", "approval_status"})

    if "dropbox_url" in updates and updates["dropbox_url"]:
        existing = (
            db.query(Poster)
            .filter(Poster.dropbox_url == updates["dropbox_url"], Poster.id != poster_id)
            .first()
        )
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, "A poster record with this Dropbox URL already exists")

    for key, value in updates.items():
        setattr(poster, key, value)

    if payload.workflow_steps is not None:
        poster.workflow_steps = [step.model_dump() for step in payload.workflow_steps]
    if payload.approval_status is not None:
        from app.core.models import ApprovalStatus

        poster.approval_status = ApprovalStatus(payload.approval_status)

    db.commit()
    record_audit(
        actor=current_user.username, action="poster_updated",
        resource_type="poster", resource_id=poster.id, detail={"fields": list(updates.keys())},
    )
    return poster


@router.delete("/{poster_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poster(
    poster_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")
    db.delete(poster)
    db.commit()
    record_audit(
        actor=current_user.username, action="poster_deleted",
        resource_type="poster", resource_id=poster_id,
    )
