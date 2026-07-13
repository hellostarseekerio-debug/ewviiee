"""Dashboard summary endpoint - aggregates real data already tracked
elsewhere (documents, posters, users, AI usage log, audit log) into one
response for the frontend's landing page, rather than the frontend making
half a dozen separate calls and computing counts client-side."""
from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas import DashboardStats
from app.core.database import get_db
from app.core.models import AIUsageLog, AuditLog, Document, DocumentStatus, ExportJob, Poster, PosterStatus, User
from app.posters.duplicates import find_all_duplicates

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Actions counted toward "downloads today" - every place this platform
# actually hands a file to a user, kept as a named list rather than a
# magic string scattered across the query so it stays in sync with
# app/api/routes/posters.py and app/api/routes/documents.py's audit calls.
_DOWNLOAD_ACTIONS = ["poster_export_zip", "poster_export_csv", "document_downloaded"]


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    documents_by_status = dict(
        db.query(Document.status, func.count(Document.id))
        .filter(Document.is_deleted.is_(False))
        .group_by(Document.status)
        .all()
    )
    documents_by_approval_status = dict(
        db.query(Document.approval_status, func.count(Document.id))
        .filter(Document.is_deleted.is_(False))
        .group_by(Document.approval_status)
        .all()
    )
    total_documents = db.query(Document).filter(Document.is_deleted.is_(False)).count()

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()

    ai_usage_total = db.query(AIUsageLog).count()
    ai_usage_cloud = db.query(AIUsageLog).filter(AIUsageLog.is_cloud_provider.is_(True)).count()
    ai_usage_local = ai_usage_total - ai_usage_cloud

    recent_events = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all()
    recent_activity = [
        {
            "actor": e.actor,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "success": e.success,
            "created_at": e.created_at.isoformat(),
        }
        for e in recent_events
    ]

    # --- Posters -------------------------------------------------------------
    total_posters = db.query(Poster).count()
    posters_by_district = dict(
        db.query(Poster.district, func.count(Poster.id))
        .filter(Poster.district.isnot(None))
        .group_by(Poster.district)
        .all()
    )
    posters_by_estate = dict(
        db.query(Poster.estate, func.count(Poster.id))
        .filter(Poster.estate.isnot(None))
        .group_by(Poster.estate)
        .all()
    )
    posters_by_status = {
        k.value if hasattr(k, "value") else k: v
        for k, v in db.query(Poster.status, func.count(Poster.id)).group_by(Poster.status).all()
    }

    recent_posters = db.query(Poster).order_by(Poster.created_at.desc()).limit(10).all()
    recent_poster_uploads = [
        {
            "id": p.id,
            "title": p.poster_title,
            "district": p.district,
            "estate": p.estate,
            "created_at": p.created_at.isoformat(),
        }
        for p in recent_posters
    ]

    broken_dropbox_links = db.query(Poster).filter(Poster.dropbox_link_broken.is_(True)).count()
    duplicate_poster_groups = len(find_all_duplicates(db))

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    downloads_today = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(_DOWNLOAD_ACTIONS), AuditLog.created_at >= today_start)
        .count()
    )

    pending_reviews = (
        db.query(Poster)
        .filter(Poster.status.in_([PosterStatus.PENDING_REVIEW, PosterStatus.NEEDS_CHANGES]))
        .count()
        + db.query(Document)
        .filter(Document.is_deleted.is_(False), Document.status == DocumentStatus.REVIEW)
        .count()
    )

    most_active_rows = (
        db.query(AuditLog.actor, func.count(AuditLog.id).label("action_count"))
        .filter(AuditLog.actor.isnot(None))
        .group_by(AuditLog.actor)
        .order_by(func.count(AuditLog.id).desc())
        .limit(5)
        .all()
    )
    most_active_users = [{"actor": actor, "action_count": count} for actor, count in most_active_rows]

    export_storage_bytes = (
        db.query(func.coalesce(func.sum(ExportJob.file_size_bytes), 0)).scalar() or 0
    )

    return DashboardStats(
        total_documents=total_documents,
        documents_by_status={k.value if hasattr(k, "value") else k: v for k, v in documents_by_status.items()},
        documents_by_approval_status={
            k.value if hasattr(k, "value") else k: v for k, v in documents_by_approval_status.items()
        },
        total_users=total_users,
        active_users=active_users,
        ai_usage_total=ai_usage_total,
        ai_usage_cloud=ai_usage_cloud,
        ai_usage_local=ai_usage_local,
        recent_activity=recent_activity,
        total_posters=total_posters,
        posters_by_district=posters_by_district,
        posters_by_estate=posters_by_estate,
        posters_by_status=posters_by_status,
        recent_poster_uploads=recent_poster_uploads,
        broken_dropbox_links=broken_dropbox_links,
        duplicate_poster_groups=duplicate_poster_groups,
        downloads_today=downloads_today,
        pending_reviews=pending_reviews,
        most_active_users=most_active_users,
        export_storage_bytes=int(export_storage_bytes),
    )
