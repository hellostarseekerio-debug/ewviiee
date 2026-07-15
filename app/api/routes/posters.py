"""Poster Archive endpoints - paste-text Dropbox link management.

Security: import/create/edit require Editor+, delete requires Admin+ (same
role thresholds used for the Documents resource). Status changes require
Reviewer+ for the approve/reject verdicts themselves, and Editor+ for
every other transition (draft->pending_review, publish, archive, resubmit)
- see app/posters/status.py for the full transition graph and role rules.
Every mutating action is recorded in the audit log, matching the rest of
the API.
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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_rule_engine, require_role
from app.api.rate_limit import limiter
from app.api.schemas import (
    DuplicateGroupOut,
    LinkVerifyResultOut,
    PosterBulkDeleteRequest,
    PosterBulkFieldUpdateRequest,
    PosterBulkMoveRequest,
    PosterBulkStatusRequest,
    PosterCreateRequest,
    PosterDebugResponse,
    PosterImportRequest,
    PosterImportResponse,
    PosterImportResult,
    PosterLinkHistoryOut,
    PosterListResponse,
    PosterOut,
    PosterReparseResponse,
    PosterReparseResult,
    PosterReparseSkip,
    PosterStatusChangeRequest,
    PosterUpdateRequest,
    PosterZipExportRequest,
    ZipExportAcceptedResponse,
)
from app.core.config import get_settings
from app.core.database import get_db, session_scope
from app.core.logging_config import get_logger, record_audit
from app.core.models import ExportJob, ExportJobStatus, Poster, PosterLinkHistory, PosterStatus, UserRole
from app.core.security import role_rank
from app.core.status_workflow import StatusTransitionError
from app.folders.service import FolderNotFoundError, get_folder_or_raise, subtree_folder_ids
from app.folders.suggestions import resolve_or_create_poster_folder
from app.posters.corrections import record_correction
from app.posters.duplicates import find_all_duplicates
from app.posters.parser import parse_block, parse_poster_text
from app.posters.status import approval_status_for, required_role_for_transition, validate_poster_transition
from app.posters.validation import InvalidDropboxUrlError, assert_valid_dropbox_url
from app.rules.engine import RuleEngine
from app.storage.archive_zip import ExportableRecord, ZipExportLimitError, build_zip_export
from app.storage.download_service import build_default_download_service
from app.storage.providers.dropbox import DropboxStorageProvider

router = APIRouter(prefix="/api/posters", tags=["posters"])
logger = get_logger(__name__)


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
    repeat is reported back as a duplicate, not an error).

    Each record is auto-filed into a Year -> Month -> District -> Estate
    folder (app/folders/suggestions.py), created on demand if it doesn't
    exist yet - unless `payload.folder_id` is set, which files the whole
    batch there instead."""
    if payload.folder_id:
        get_folder_or_raise(db, payload.folder_id)  # 404s cleanly rather than saving a dangling folder_id

    parsed_records = parse_poster_text(payload.text, rule_engine, db=db)

    results: list[PosterImportResult] = []
    to_insert: list[Poster] = []
    seen_in_batch: set[str] = set()
    # Many records in one paste commonly share a date/district/estate combo
    # (a batch of notices for the same estate on the same day) - cache the
    # resolved folder per unique segment tuple so a 1,000-record paste
    # doesn't repeat the same get-or-create folder lookup 1,000 times.
    folder_cache: dict[tuple[str | None, str | None, str | None], str | None] = {}

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

        if payload.folder_id:
            folder_id = payload.folder_id
        else:
            cache_key = (
                parsed.district,
                parsed.estate,
                parsed.poster_type,
                parsed.document_date.strftime("%Y-%m") if parsed.document_date else None,
            )
            if cache_key not in folder_cache:
                folder_cache[cache_key] = resolve_or_create_poster_folder(
                    db,
                    folder_id_override=None,
                    district=parsed.district,
                    estate=parsed.estate,
                    poster_type=parsed.poster_type,
                    document_date=parsed.document_date,
                    created_by=current_user.username,
                )
            folder_id = folder_cache[cache_key]

        poster = Poster(
            district=parsed.district,
            region=parsed.region,
            estate=parsed.estate,
            poster_title=parsed.poster_title,
            poster_type=parsed.poster_type,
            route_number=parsed.route_number,
            politicians=parsed.politicians or None,
            document_date=parsed.document_date,
            date_to=parsed.date_to,
            dropbox_url=parsed.dropbox_url,
            language=parsed.language,
            keywords=parsed.keywords or None,
            source_text=parsed.source_text,
            folder_id=folder_id,
            version=parsed.version,
            government_department=parsed.government_department,
            needs_review=parsed.needs_review,
            source="paste_import",
            extraction_confidence=parsed.field_confidence or None,
            extraction_sources=parsed.field_sources or None,
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
    *,
    db: Session | None = None,
    folder_id: str | None = None,
    recursive: bool = True,
    poster_status: str | None = None,
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
    if folder_id:
        assert db is not None, "db is required when filtering by folder_id"
        folder = get_folder_or_raise(db, folder_id)
        folder_ids = subtree_folder_ids(db, folder, include_self=True) if recursive else [folder.id]
        query = query.filter(Poster.folder_id.in_(folder_ids))
    if poster_status:
        try:
            query = query.filter(Poster.status == PosterStatus(poster_status))
        except ValueError:
            valid = ", ".join(s.value for s in PosterStatus)
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown status '{poster_status}' (valid: {valid})")
    return query


@router.get("/search", response_model=PosterListResponse)
def search_posters(
    q: str | None = Query(default=None, description="Free-text search across title/district/estate/route/keywords/dropbox URL"),
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    folder_id: str | None = Query(default=None, description="Filter to one folder (and its subfolders unless recursive=false)"),
    recursive: bool = Query(default=True),
    poster_status: str | None = Query(default=None, alias="status"),
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
                Poster.region.ilike(like),
                Poster.estate.ilike(like),
                Poster.poster_type.ilike(like),
                Poster.route_number.ilike(like),
                Poster.dropbox_url.ilike(like),
                Poster.notes.ilike(like),
                Poster.campaign_name.ilike(like),
                Poster.government_department.ilike(like),
            )
        )
    try:
        filtered_query = _apply_filters(
            query, district, poster_type, date_from, date_to, has_dropbox,
            db=db, folder_id=folder_id, recursive=recursive, poster_status=poster_status,
        )
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    total = filtered_query.count()

    # Fuzzy fallback: an exact ILIKE match found nothing, but the query
    # might just be a typo, OCR noise, or mixed Chinese/English spelling -
    # exactly the case app/rules/fuzzy.py already exists to handle for
    # district/estate resolution. Only runs on a genuine zero-result exact
    # search, so the common case (an exact match exists) pays no extra
    # cost; bounded to the same result-set size other searches are, so it
    # can't become an unbounded full-archive scan.
    if q and total == 0:
        return _fuzzy_fallback_search(
            db, q,
            district=district, poster_type=poster_type, date_from=date_from, date_to=date_to,
            has_dropbox=has_dropbox, folder_id=folder_id, recursive=recursive, poster_status=poster_status,
            skip=skip, limit=limit,
        )

    results = filtered_query.order_by(Poster.created_at.desc()).offset(skip).limit(limit).all()
    return PosterListResponse(total=total, results=results)


_FUZZY_SEARCH_SCAN_LIMIT = 2000
_FUZZY_SEARCH_THRESHOLD = 0.6


def _fuzzy_fallback_search(
    db: Session,
    q: str,
    *,
    district: str | None,
    poster_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    has_dropbox: bool | None,
    folder_id: str | None,
    recursive: bool,
    poster_status: str | None,
    skip: int,
    limit: int,
) -> PosterListResponse:
    from app.rules.fuzzy import similarity

    candidates_query = _apply_filters(
        db.query(Poster), district, poster_type, date_from, date_to, has_dropbox,
        db=db, folder_id=folder_id, recursive=recursive, poster_status=poster_status,
    )
    candidates = (
        candidates_query.order_by(Poster.created_at.desc()).limit(_FUZZY_SEARCH_SCAN_LIMIT).all()
    )

    scored: list[tuple[float, Poster]] = []
    for poster in candidates:
        fields = [poster.poster_title, poster.district, poster.estate, *(poster.keywords or [])]
        best = max((similarity(q, f) for f in fields if f), default=0.0)
        if best >= _FUZZY_SEARCH_THRESHOLD:
            scored.append((best, poster))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    total = len(scored)
    page = [poster for _, poster in scored[skip : skip + limit]]
    return PosterListResponse(total=total, results=page)


@router.get("/export")
def export_posters_csv(
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    folder_id: str | None = Query(default=None),
    recursive: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        query = _apply_filters(
            db.query(Poster), district, poster_type, date_from, date_to, has_dropbox,
            db=db, folder_id=folder_id, recursive=recursive,
        )
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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


def _resolve_export_posters(db: Session, payload: PosterZipExportRequest) -> list[Poster]:
    """Selection precedence: explicit `ids` (selected files) > `folder_id`
    (current folder, optionally recursive) > the plain filter fields
    (search results) > no filters at all (the entire archive)."""
    if payload.ids:
        return db.query(Poster).filter(Poster.id.in_(payload.ids)).all()

    query = db.query(Poster)
    if payload.q:
        like = f"%{payload.q}%"
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
    query = _apply_filters(
        query, payload.district, payload.poster_type, payload.date_from, payload.date_to, payload.has_dropbox,
        db=db, folder_id=payload.folder_id, recursive=payload.recursive,
    )
    return query.order_by(Poster.created_at.desc()).all()


def _posters_to_exportable(posters: list[Poster]) -> list[ExportableRecord]:
    return [
        ExportableRecord(
            id=p.id,
            title=p.poster_title,
            file_reference=p.dropbox_url,
            folder_id=p.folder_id,
            metadata={
                "district": p.district or "",
                "estate": p.estate or "",
                "poster_type": p.poster_type or "",
                "route_number": p.route_number or "",
                "document_date": p.document_date.isoformat() if p.document_date else "",
                "status": p.status.value,
                "dropbox_url": p.dropbox_url or "",
            },
        )
        for p in posters
    ]


def _run_zip_export_job(job_id: str, poster_ids: list[str]) -> None:
    """Background counterpart of the synchronous path below - runs after
    the HTTP response has already gone out (202 Accepted + job id), in its
    own DB session since the request-scoped one is closed by then. Never
    raises out of this function: any failure is recorded on the job row so
    the client's poll sees a FAILED status with a reason, not a silently
    stuck PENDING job."""
    settings = get_settings()
    with session_scope() as db:
        job = db.get(ExportJob, job_id)
        if job is None:
            return
        job.status = ExportJobStatus.RUNNING
        db.commit()
        try:
            posters = db.query(Poster).filter(Poster.id.in_(poster_ids)).all()
            records = _posters_to_exportable(posters)
            download_service = build_default_download_service(settings)
            result = build_zip_export(
                db, records, download_service=download_service,
                max_files=settings.zip_export_max_files, max_total_bytes=settings.zip_export_max_total_bytes,
                archive_label="Poster Archive",
            )
            settings.export_jobs_dir.mkdir(parents=True, exist_ok=True)
            file_path = settings.export_jobs_dir / f"{job_id}.zip"
            file_path.write_bytes(result.buffer)
            job.status = ExportJobStatus.COMPLETED
            job.included_items = result.included
            job.file_path = str(file_path)
            job.file_size_bytes = len(result.buffer)
            job.completed_at = datetime.utcnow()
            db.commit()
        except Exception as exc:  # noqa: BLE001 - a background job must never crash silently stuck
            job.status = ExportJobStatus.FAILED
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.utcnow()
            db.commit()


@router.post("/export/zip")
def export_posters_zip(
    payload: PosterZipExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Supports all four required export shapes via `payload` (see
    _resolve_export_posters): selected files (`ids`), the current folder
    (`folder_id` [+ `recursive`]), search results (the filter fields), or
    the entire archive (no fields at all). Small/medium exports stream
    back immediately; anything over `zip_export_sync_threshold` is handed
    to a background ExportJob instead, so a huge "export everything"
    request can't tie up an HTTP worker for minutes - see
    docs/ARCHITECTURE_REVIEW_2026-07.md's risk #1 on this exact hazard."""
    settings = get_settings()
    try:
        posters = _resolve_export_posters(db, payload)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    if not posters:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching poster records to export")
    if len(posters) > settings.zip_export_max_files:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Export exceeds the {settings.zip_export_max_files}-file limit ({len(posters)} requested)",
        )

    if len(posters) <= settings.zip_export_sync_threshold:
        download_service = build_default_download_service(settings)
        try:
            result = build_zip_export(
                db, _posters_to_exportable(posters), download_service=download_service,
                max_files=settings.zip_export_max_files, max_total_bytes=settings.zip_export_max_total_bytes,
                archive_label="Poster Archive",
            )
        except ZipExportLimitError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        record_audit(
            actor=current_user.username, action="poster_export_zip",
            detail={"requested": len(posters), "included": result.included, "background": False},
        )
        filename = f"posters_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        return StreamingResponse(
            iter([result.buffer]), media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    job = ExportJob(
        resource_type="poster", status=ExportJobStatus.PENDING,
        requested_by=current_user.username, total_items=len(posters),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_run_zip_export_job, job.id, [p.id for p in posters])
    record_audit(
        actor=current_user.username, action="poster_export_zip_queued",
        resource_type="export_job", resource_id=job.id, detail={"requested": len(posters)},
    )
    accepted = ZipExportAcceptedResponse(job_id=job.id, status=job.status.value, total_items=job.total_items)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=jsonable_encoder(accepted))


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


@router.post("/bulk-move", status_code=status.HTTP_200_OK)
def bulk_move_posters(
    payload: PosterBulkMoveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    """Moves every listed poster to `folder_id` in one statement -
    `folder_id: null` moves them to the root (unfiled)."""
    if payload.folder_id:
        try:
            get_folder_or_raise(db, payload.folder_id)
        except FolderNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    moved = (
        db.query(Poster)
        .filter(Poster.id.in_(payload.ids))
        .update({"folder_id": payload.folder_id}, synchronize_session=False)
    )
    db.commit()
    record_audit(
        actor=current_user.username, action="poster_bulk_moved",
        detail={"requested": len(payload.ids), "moved": moved, "folder_id": payload.folder_id},
    )
    return {"moved": moved}


@router.post("/bulk-update", status_code=status.HTTP_200_OK)
def bulk_update_posters(
    payload: PosterBulkFieldUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    """Bulk retag/reclassify: change district/estate/poster_type and/or
    append keywords across every listed record in as few statements as
    possible. Fields left unset in the payload are untouched."""
    field_updates = {
        k: v
        for k, v in {"district": payload.district, "estate": payload.estate, "poster_type": payload.poster_type}.items()
        if v is not None
    }
    updated = 0
    if field_updates:
        updated = (
            db.query(Poster).filter(Poster.id.in_(payload.ids)).update(field_updates, synchronize_session=False)
        )

    if payload.add_keywords:
        posters = db.query(Poster).filter(Poster.id.in_(payload.ids)).all()
        for poster in posters:
            existing = poster.keywords or []
            merged = existing + [k for k in payload.add_keywords if k not in existing]
            poster.keywords = merged
        updated = max(updated, len(posters))

    db.commit()
    record_audit(
        actor=current_user.username, action="poster_bulk_updated",
        detail={"requested": len(payload.ids), "updated": updated, "fields": list(field_updates.keys())},
    )
    return {"updated": updated}


# Every field the parser can fill that a blank/needs-review record might
# be missing - re-checked per record in POST /api/posters/reparse. Kept as
# a single source of truth so the "is this record a reparse candidate?"
# filter and the "which fields did we just fill in?" diff use exactly the
# same field list.
_REPARSEABLE_FIELDS = ["district", "region", "estate", "poster_type", "route_number", "poster_title"]


@router.post("/reparse", response_model=PosterReparseResponse)
def reparse_posters(
    db: Session = Depends(get_db),
    rule_engine: RuleEngine = Depends(get_rule_engine),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    """Re-runs the *current* parser against every already-imported record's
    permanently-stored `source_text`, filling in only fields that are
    still blank - never touching a value already present (whether it came
    from the original parse or a staff correction).

    Why this exists: parsing only ever happens once, at import time. Every
    parser improvement shipped since a record was first imported has *no
    effect on that record* until it's explicitly re-parsed - the record
    keeps whatever the parser produced back when it was pasted in,
    permanently, regardless of how much better the parser has since
    gotten. This is the backfill operation that actually applies those
    improvements to existing data; without it, a better parser only ever
    helps future imports.

    Only records with `source_text` (paste-import origin) and at least one
    of the reparseable fields blank, or flagged `needs_review`, are
    candidates - a manually-created or already-fully-populated record is
    never touched."""
    candidates = (
        db.query(Poster)
        .filter(Poster.source_text.isnot(None))
        .filter(
            or_(
                Poster.needs_review.is_(True),
                *[getattr(Poster, f).is_(None) for f in _REPARSEABLE_FIELDS],
            )
        )
        .all()
    )
    logger.info(
        "poster_reparse.candidates_found",
        count=len(candidates),
        poster_ids=[p.id for p in candidates],
    )

    results: list[PosterReparseResult] = []
    skipped: list[PosterReparseSkip] = []
    fields_updated: dict[str, int] = {}
    for poster in candidates:
        parsed = parse_block(poster.source_text, rule_engine, db=db)
        if parsed is None:
            logger.info("poster_reparse.row_skipped", poster_id=poster.id, reason="parser_returned_none")
            skipped.append(PosterReparseSkip(id=poster.id, reason="parser_returned_none"))
            continue

        fields_filled: dict[str, str] = {}
        before_after: dict[str, dict[str, str | None]] = {}
        for field in _REPARSEABLE_FIELDS:
            current_value = getattr(poster, field)
            new_value = getattr(parsed, field)
            if not current_value and new_value:
                setattr(poster, field, new_value)
                fields_filled[field] = parsed.field_sources.get(field, "regex")
                before_after[field] = {"before": current_value, "after": new_value}

        if parsed.politicians and not poster.politicians:
            poster.politicians = parsed.politicians
            fields_filled["politicians"] = "rule_engine"
            before_after["politicians"] = {"before": None, "after": ",".join(parsed.politicians)}
        if parsed.document_date and not poster.document_date:
            poster.document_date = parsed.document_date
            fields_filled["document_date"] = "regex"
            before_after["document_date"] = {"before": None, "after": str(parsed.document_date)}

        if fields_filled:
            # Merge, never overwrite, the confidence/source bookkeeping -
            # a field already populated (and so left alone above) keeps
            # whatever confidence/source it already had.
            poster.extraction_confidence = {**(poster.extraction_confidence or {}), **{
                f: parsed.field_confidence.get(f, 0.0) for f in fields_filled
            }}
            poster.extraction_sources = {**(poster.extraction_sources or {}), **fields_filled}
            # A record only stops needing review once re-parsing actually
            # resolved it - never flip an already-fine record to needing
            # review, and never leave a now-resolved one still flagged.
            if poster.needs_review and not parsed.needs_review:
                poster.needs_review = False
            for field in fields_filled:
                fields_updated[field] = fields_updated.get(field, 0) + 1
            logger.info(
                "poster_reparse.row_updated",
                poster_id=poster.id,
                fields_filled=fields_filled,
                before_after=before_after,
            )
            results.append(PosterReparseResult(id=poster.id, fields_filled=fields_filled))
        else:
            # The parser ran successfully but produced nothing that the row
            # was actually missing - e.g. it already had every reparseable
            # field, or the parser's answer for each still-blank field was
            # itself blank (source_text lacks that signal).
            reason = "no_new_values"
            logger.info("poster_reparse.row_skipped", poster_id=poster.id, reason=reason)
            skipped.append(PosterReparseSkip(id=poster.id, reason=reason))

    db.commit()
    logger.info(
        "poster_reparse.complete",
        scanned=len(candidates),
        updated=len(results),
        unchanged=len(skipped),
        fields_updated=fields_updated,
    )
    record_audit(
        actor=current_user.username,
        action="poster_reparse",
        detail={"scanned": len(candidates), "updated": len(results), "fields_updated": fields_updated},
    )
    return PosterReparseResponse(
        scanned=len(candidates),
        updated=len(results),
        unchanged=len(skipped),
        fields_updated=fields_updated,
        results=results,
        skipped=skipped,
    )


# Fields the frontend table (frontend/app/(app)/posters/page.tsx) actually
# reads for its row display, and the literal fallback string it substitutes
# when that field is falsy - kept in sync by hand since this is a temporary
# diagnostic route, not a real API contract.
_RENDERED_FIELD_FALLBACKS = {
    "poster_title": "(untitled)",
    "poster_type": None,
    "district": "—",
    "estate": "—",
    "route_number": "—",
    "document_date": "—",
    "status": None,
    "dropbox_url": None,
}


@router.get("/debug/{poster_id}", response_model=PosterDebugResponse)
def debug_poster(poster_id: str, db: Session = Depends(get_db), current_user=Depends(require_role(UserRole.EDITOR))):
    """TEMPORARY diagnostic route added to trace a single poster's value
    through every pipeline stage - raw DB row, serialized API response, and
    the fields/fallbacks the frontend table actually renders - to find the
    first point where a value goes null/blank. Remove once the data-flow
    investigation it supports is closed out; not part of the stable API."""
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")

    database_values = {
        column.name: getattr(poster, column.name) for column in Poster.__table__.columns
    }
    api_response = jsonable_encoder(PosterOut.model_validate(poster))

    rendered_fields = {}
    for field, fallback in _RENDERED_FIELD_FALLBACKS.items():
        raw = api_response.get(field)
        rendered_fields[field] = {
            "raw_value": raw,
            "displayed_as": raw if raw else fallback,
        }
    # The table's district/estate column joins both with " · " and falls
    # back to "—" only when *both* are empty - mirror that combined view too.
    district, estate = api_response.get("district"), api_response.get("estate")
    rendered_fields["district_estate_combined"] = {
        "raw_value": [district, estate],
        "displayed_as": " · ".join(v for v in (district, estate) if v) or "—",
    }

    return PosterDebugResponse(
        database=jsonable_encoder(database_values),
        api_response=api_response,
        rendered_fields=rendered_fields,
    )


@router.post("/bulk-status", status_code=status.HTTP_200_OK)
def bulk_change_poster_status(
    payload: PosterBulkStatusRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.REVIEWER)),
):
    """Bulk counterpart of POST /{poster_id}/status - same validated
    transition graph and role gate per record, applied individually so one
    poster with an invalid transition never blocks the rest of the batch."""
    try:
        new_status = PosterStatus(payload.status)
    except ValueError:
        valid = ", ".join(s.value for s in PosterStatus)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown status '{payload.status}' (valid: {valid})")

    required_role = required_role_for_transition(new_status)
    if role_rank(current_user.role) < role_rank(required_role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Changing status to '{new_status.value}' requires the {required_role.value} role or above",
        )
    is_admin_force = payload.force and role_rank(current_user.role) >= role_rank(UserRole.ADMIN)

    changed = 0
    skipped: list[str] = []
    posters = db.query(Poster).filter(Poster.id.in_(payload.ids)).all()
    for poster in posters:
        try:
            validate_poster_transition(poster.status, new_status, force=is_admin_force)
        except StatusTransitionError:
            skipped.append(poster.id)
            continue
        poster.status = new_status
        poster.approval_status = approval_status_for(new_status)
        changed += 1
    db.commit()

    record_audit(
        actor=current_user.username, action="poster_bulk_status_changed",
        detail={"requested": len(payload.ids), "changed": changed, "skipped": len(skipped), "to": new_status.value},
    )
    return {"changed": changed, "skipped": skipped}


@router.get("/duplicates", response_model=list[DuplicateGroupOut])
def list_duplicate_posters(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Surfaces exact-Dropbox-link and similar-title duplicate groups (see
    app/posters/duplicates.py) for manual merge review - never merges
    automatically, since deciding which record is authoritative is a
    judgment call this endpoint deliberately leaves to a human."""
    groups = find_all_duplicates(db)
    return [DuplicateGroupOut(reason=g.reason, poster_ids=g.poster_ids, detail=g.detail) for g in groups]


@router.post("/{poster_id}/verify-link", response_model=LinkVerifyResultOut)
def verify_poster_link(
    poster_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")
    if not poster.dropbox_url:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This record has no Dropbox link to verify")

    provider = DropboxStorageProvider()
    is_ok = provider.verify(poster.dropbox_url) if provider.can_handle(poster.dropbox_url) else False
    poster.dropbox_link_broken = not is_ok
    poster.dropbox_last_verified_at = datetime.utcnow()
    db.commit()

    record_audit(
        actor=current_user.username, action="poster_link_verified",
        resource_type="poster", resource_id=poster.id, detail={"broken": poster.dropbox_link_broken},
    )
    return LinkVerifyResultOut(
        poster_id=poster.id,
        dropbox_link_broken=poster.dropbox_link_broken,
        dropbox_last_verified_at=poster.dropbox_last_verified_at,
    )


@router.get("/{poster_id}/link-history", response_model=list[PosterLinkHistoryOut])
def get_poster_link_history(poster_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")
    return poster.link_history


@router.get("", response_model=PosterListResponse)
def list_posters(
    district: str | None = None,
    poster_type: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_dropbox: bool | None = None,
    folder_id: str | None = Query(default=None, description="Filter to one folder (and its subfolders unless recursive=false)"),
    recursive: bool = Query(default=True),
    poster_status: str | None = Query(default=None, alias="status"),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|document_date|district|poster_title)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    try:
        query = _apply_filters(
            db.query(Poster), district, poster_type, date_from, date_to, has_dropbox,
            db=db, folder_id=folder_id, recursive=recursive, poster_status=poster_status,
        )
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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

    if payload.folder_id:
        try:
            get_folder_or_raise(db, payload.folder_id)
        except FolderNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    poster = Poster(**payload.model_dump(exclude={"workflow_steps", "folder_id"}))
    if payload.workflow_steps is not None:
        poster.workflow_steps = [step.model_dump() for step in payload.workflow_steps]
    poster.folder_id = resolve_or_create_poster_folder(
        db,
        folder_id_override=payload.folder_id,
        district=payload.district,
        estate=payload.estate,
        poster_type=payload.poster_type,
        document_date=payload.document_date,
        created_by=current_user.username,
    )
    poster.source = poster.source or "manual"
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

    if updates.get("folder_id"):
        try:
            get_folder_or_raise(db, updates["folder_id"])
        except FolderNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    if "dropbox_url" in updates and updates["dropbox_url"] != poster.dropbox_url:
        # Preserve history before the old value is overwritten - "if a
        # Dropbox link changes, preserve history" is a hard requirement,
        # not best-effort.
        db.add(
            PosterLinkHistory(
                poster_id=poster.id,
                old_url=poster.dropbox_url,
                new_url=updates["dropbox_url"],
                changed_by=current_user.username,
            )
        )
        # A changed link hasn't been re-verified yet - stale verification
        # state would be actively misleading.
        poster.dropbox_link_broken = None
        poster.dropbox_last_verified_at = None

    if "district" in updates and updates["district"] and poster.estate:
        # A correction is only worth remembering when it's actually
        # teaching the parser something new - a low-confidence/blank
        # district being confirmed/filled in, not a confident match being
        # second-guessed for unrelated reasons. See app/posters/
        # corrections.py: this is what lets an estate the parser can't yet
        # place get its district auto-filled on every future import that
        # mentions it, without a config edit or a redeploy.
        old_confidence = (poster.extraction_confidence or {}).get("district")
        was_low_confidence = poster.district is None or (old_confidence is not None and old_confidence < 0.8)
        if was_low_confidence and updates["district"] != poster.district:
            record_correction(
                db,
                key_type="estate_name",
                key_value=poster.estate,
                field="district",
                value=updates["district"],
                corrected_by=current_user.username,
            )

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


@router.post("/{poster_id}/status", response_model=PosterOut)
def change_poster_status(
    poster_id: str,
    payload: PosterStatusChangeRequest,
    db: Session = Depends(get_db),
    # REVIEWER is the lowest bar among all valid transitions (approve/
    # reject) - _ROLE_RANK ranks Reviewer below Editor, so this reads as
    # "Reviewer, Editor, or Admin", matching Document's approve/reject
    # convention. Transitions that need more than Reviewer (everything
    # except approve/reject) are checked explicitly below.
    current_user=Depends(require_role(UserRole.REVIEWER)),
):
    """Moves a poster through its status lifecycle (draft -> pending_review
    -> approved -> published -> archived, with rejected/resubmit branches -
    see app/posters/status.py). Only an Admin's `force: true` can skip the
    transition graph, e.g. to correct a mistake; the per-transition role
    requirement still applies even when forcing."""
    poster = db.get(Poster, poster_id)
    if poster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster record not found")

    try:
        new_status = PosterStatus(payload.status)
    except ValueError:
        valid = ", ".join(s.value for s in PosterStatus)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown status '{payload.status}' (valid: {valid})")

    required_role = required_role_for_transition(new_status)
    if role_rank(current_user.role) < role_rank(required_role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Changing status to '{new_status.value}' requires the {required_role.value} role or above",
        )

    is_admin_force = payload.force and role_rank(current_user.role) >= role_rank(UserRole.ADMIN)
    try:
        validate_poster_transition(poster.status, new_status, force=is_admin_force)
    except StatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    previous_status = poster.status
    poster.status = new_status
    poster.approval_status = approval_status_for(new_status)
    db.commit()

    record_audit(
        actor=current_user.username,
        action="poster_status_changed",
        resource_type="poster",
        resource_id=poster.id,
        detail={
            "from": previous_status.value,
            "to": new_status.value,
            "forced": is_admin_force,
            "notes": payload.notes,
        },
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
