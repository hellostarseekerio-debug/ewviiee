"""Core ORM models shared by every workflow/plugin."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class DocumentStatus(str, enum.Enum):
    IMPORTED = "imported"
    CLASSIFIED = "classified"
    OCR_DONE = "ocr_done"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    GENERATED = "generated"
    REVIEW = "review"
    EXPORTED = "exported"
    ARCHIVED = "archived"
    FAILED = "failed"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Document(Base):
    """A single document tracked through the system, with full metadata."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(512))
    source_path: Mapped[str] = mapped_column(String(1024))
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), default=DocumentStatus.IMPORTED, index=True
    )

    district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    estate: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    politician: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    reference_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    document_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)

    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Approval / review workflow (Phase 7)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Safe/soft deletion - never physically remove a processed record on request
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Indexed: every search/listing query orders by created_at DESC - at
    # thousands of rows, an unindexed sort here forces a full-table scan.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    processing_history: Mapped[list["ProcessingEvent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_number"
    )


class ProcessingEvent(Base):
    """One entry in a document's processing history (audit trail per-document)."""

    __tablename__ = "processing_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    stage: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="processing_history")


class DocumentVersion(Base):
    """Version history for a document's generated output, enabling rollback.
    Original source documents are never modified or overwritten; each
    generation pass is recorded here as a new, immutable version."""

    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(1024))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="versions")


class WorkflowRun(Base):
    """Tracks a single execution of a workflow across a batch of documents."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_name: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default="running")
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Account lockout protection (brute-force defense)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Multi-factor authentication (TOTP). Secret is encrypted at rest via
    # SecretBox; recovery codes are bcrypt-hashed, one-time-use.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mfa_pending_secret_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mfa_recovery_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)


class SystemSetting(Base):
    """Admin-configurable runtime settings that should take effect without a
    redeploy (e.g. the cloud-AI kill switch). Falls back to Settings/.env
    defaults when a key is absent."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AIUsageLog(Base):
    """Audit trail of AI provider calls. Deliberately stores only metadata
    (provider/operation/success/timing) - never the document text or prompt
    content - so this log itself never becomes a privacy liability."""

    __tablename__ = "ai_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    is_cloud_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AuditLog(Base):
    """Immutable audit trail for every action taken in the system."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(256))
    resource_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Poster(Base):
    """A single poster/notice record parsed from a pasted block of text
    (title + metadata + a Dropbox link) via the Poster Archive's paste-text
    import - see app/posters/parser.py. Deliberately independent of the
    `documents` table: a poster record here is a *reference* to a Dropbox
    folder, not a document this platform has itself processed, and is
    parsed from unstructured pasted text rather than an uploaded file.

    Future-compatibility fields (ai_summary, ocr_text, approval_status,
    attachments) are included now, all nullable, specifically so that
    later automation (uploading a generated PDF, running OCR, requiring
    review) can attach to an existing row without another migration -
    they default to unused/empty and cost nothing until populated.
    """

    __tablename__ = "posters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    district: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    estate: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    poster_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    poster_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    route_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    document_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Unique so the same Dropbox link can never be stored twice (the import
    # endpoint also pre-checks this in bulk before inserting, so a large
    # paste never fails outright over one repeated link - see
    # app/api/routes/posters.py). Nullable to support the "Missing Dropbox"
    # filter (a record added/edited without a link yet) - a standard SQL
    # UNIQUE constraint already treats every NULL as distinct from every
    # other NULL, so multiple link-less rows coexist without conflict while
    # any two *equal* non-null URLs still do.
    dropbox_url: Mapped[str | None] = mapped_column(String(1024), unique=True, nullable=True, index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The exact pasted block this record was parsed from, kept verbatim so
    # a human can always re-check what the parser saw if a field looks
    # wrong - never modified after import.
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured, ordered workflow instructions ({"step": 1, "action": "...",
    # "detail": "..."}), e.g. "Step 1: Generate application PDF" - stored as
    # data (not a plain-text blob) so a future automation stage can execute
    # or display them without re-parsing free text.
    workflow_steps: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # --- Future-compatibility columns (see class docstring) -----------------
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING, index=True
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
