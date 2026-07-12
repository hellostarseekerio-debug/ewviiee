"""Dashboard summary endpoint - aggregates real data already tracked
elsewhere (documents, users, AI usage log, audit log) into one response
for the frontend's landing page, rather than the frontend making half a
dozen separate calls and computing counts client-side."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas import DashboardStats
from app.core.database import get_db
from app.core.models import AIUsageLog, AuditLog, Document, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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

    recent_events = (
        db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(20).all()
    )
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
    )
