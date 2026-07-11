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
    document_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    processing_history: Mapped[list["ProcessingEvent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
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
