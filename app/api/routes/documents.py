"""Document read/upload/review endpoints.

Security: uploads are validated for extension, size and magic-byte content
before ever touching disk, are written under a server-controlled directory
with a randomly generated filename (the client-supplied name is never used
as a path), and require Editor+ role. Approve/reject requires Reviewer+.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.api.rate_limit import limiter
from app.api.schemas import DocumentOut, DocumentVersionOut, ReviewDecisionRequest, RollbackRequest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.file_safety import (
    UnsafeFileError,
    assert_content_matches_extension,
    assert_extension_allowed,
    assert_size_within_limit,
    generate_storage_filename,
)
from app.core.logging_config import record_audit
from app.core.models import ApprovalStatus, Document, DocumentVersion, UserRole

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_default)
def upload_document(
    request: Request,
    file: UploadFile,
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    settings = get_settings()
    try:
        suffix = assert_extension_allowed(file.filename or "", settings.allowed_upload_extensions)
        content = file.file.read(settings.max_upload_size_bytes + 1)
        assert_size_within_limit(len(content), settings.max_upload_size_bytes)
        assert_content_matches_extension(content, suffix)
    except UnsafeFileError as exc:
        record_audit(
            actor=current_user.username,
            action="upload_rejected",
            detail={"filename": file.filename, "reason": str(exc)},
            success=False,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    storage_name = generate_storage_filename(file.filename or "upload")
    settings.local_import_root.mkdir(parents=True, exist_ok=True)
    destination = settings.local_import_root / storage_name
    destination.write_bytes(content)

    record_audit(
        actor=current_user.username,
        action="upload_saved",
        detail={"original_filename": file.filename, "stored_as": storage_name},
    )
    return {"stored_path": str(destination), "original_filename": file.filename}


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    document = db.get(Document, document_id)
    if document is None or document.is_deleted:
        raise HTTPException(404, "Document not found")
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return (
        db.query(Document)
        .filter(Document.is_deleted.is_(False))
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut])
def list_versions(document_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    document = db.get(Document, document_id)
    if document is None or document.is_deleted:
        raise HTTPException(404, "Document not found")
    return document.versions


@router.post("/{document_id}/approve", response_model=DocumentOut)
def approve_document(
    document_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.REVIEWER)),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    document.approval_status = ApprovalStatus.APPROVED
    document.reviewed_by = current_user.username
    document.reviewed_at = datetime.utcnow()
    document.review_notes = payload.notes
    db.commit()
    record_audit(
        actor=current_user.username, action="document_approved", resource_type="document",
        resource_id=document_id,
    )
    return document


@router.post("/{document_id}/reject", response_model=DocumentOut)
def reject_document(
    document_id: str,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.REVIEWER)),
):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    document.approval_status = ApprovalStatus.REJECTED
    document.reviewed_by = current_user.username
    document.reviewed_at = datetime.utcnow()
    document.review_notes = payload.notes
    db.commit()
    record_audit(
        actor=current_user.username, action="document_rejected", resource_type="document",
        resource_id=document_id, detail={"notes": payload.notes},
    )
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    """Soft delete only - the row, its processing history and generated
    files are retained (excluded from search/listing) so a mistaken
    deletion is always recoverable and the audit trail stays intact. There
    is no hard-delete endpoint by design."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    document.is_deleted = True
    document.deleted_at = datetime.utcnow()
    document.deleted_by = current_user.username
    db.commit()
    record_audit(
        actor=current_user.username, action="document_soft_deleted", resource_type="document",
        resource_id=document_id,
    )


@router.post("/{document_id}/rollback", response_model=DocumentOut)
def rollback_document(
    document_id: str,
    payload: RollbackRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    """Restores `output_path` to point at an earlier version's file. The
    earlier version's file itself is never modified - a new version row is
    recorded so the rollback itself is auditable and reversible."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    version = db.get(DocumentVersion, payload.version_id)
    if version is None or version.document_id != document_id:
        raise HTTPException(404, "Version not found for this document")
    if not Path(version.file_path).exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "Version file is missing on disk")

    next_version_number = max((v.version_number for v in document.versions), default=0) + 1
    restored_copy = Path(version.file_path).with_name(
        f"{Path(version.file_path).stem}_restored_v{next_version_number}{Path(version.file_path).suffix}"
    )
    shutil.copy2(version.file_path, restored_copy)

    db.add(
        DocumentVersion(
            document_id=document_id,
            version_number=next_version_number,
            file_path=str(restored_copy),
            checksum_sha256=version.checksum_sha256,
            created_by=current_user.username,
            notes=f"Rollback to version {version.version_number}",
        )
    )
    document.output_path = str(restored_copy)
    document.approval_status = ApprovalStatus.PENDING
    db.commit()

    record_audit(
        actor=current_user.username,
        action="document_rollback",
        resource_type="document",
        resource_id=document_id,
        detail={"restored_version": version.version_number},
    )
    return document
