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
    UniqueConstraint,
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


class PosterStatus(str, enum.Enum):
    """Poster Archive lifecycle - replaces the flat, un-actionable "Pending"
    every imported poster used to be stuck at. See app/posters/status.py for
    the allowed-transition graph and role requirements; `Poster.status` is
    the source of truth going forward, with `approval_status` kept in sync
    (via app.posters.status.approval_status_for) for one deprecation cycle
    so anything still reading the old field keeps working."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    NEEDS_CHANGES = "needs_changes"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


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

    # Real lifecycle status (draft/pending_review/approved/published/
    # rejected/archived) - see PosterStatus's docstring and
    # app/posters/status.py for the transition rules. Defaults to
    # PENDING_REVIEW to match every existing row's prior "Pending" meaning
    # (imported/created records have always been treated as awaiting
    # review, never as an unstarted draft).
    status: Mapped[PosterStatus] = mapped_column(
        SAEnum(PosterStatus), default=PosterStatus.PENDING_REVIEW, index=True
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Nullable: a poster with no folder is simply "unfiled" (shown at the
    # archive root), never an error state. See app/folders/service.py (the
    # resource-agnostic folder engine) and app/folders/suggestions.py (the
    # Year/Month/District/Estate/Poster-Type auto-filing applied at import
    # time).
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), nullable=True, index=True)

    # --- Extended metadata (Phase 2B) ----------------------------------------
    campaign_name: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    government_department: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # How this record entered the system ("paste_import" | "manual") - a
    # plain provenance tag, not extracted from text.
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    # Set when the parser couldn't confidently resolve enough fields (no
    # district, estate, or usable title) - see app/posters/parser.py's
    # confidence check. Staff should treat these as "check before trusting",
    # not as wrong; the parser never invents a value it isn't reasonably
    # sure of, so this is the honest alternative to silently guessing.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Dropbox link health (app/storage/providers/dropbox.py's verify()) -
    # None means "never checked", not "known good".
    dropbox_link_broken: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    dropbox_last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Metadata extraction engine v2 (app/posters/parser.py) --------------
    # `region` and `politicians` are auto-filled from the resolved estate's
    # EstateMetadataService bundle (app/posters/estates.py) the moment an
    # estate is recognised - never guessed independently of that lookup.
    region: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    politicians: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    date_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Per-field confidence/source (0.0-1.0, "regex" | "rule_engine" | "ai" |
    # "default") - lets a future UI show a warning icon on exactly the
    # fields that were low-confidence or AI-guessed, instead of an
    # all-or-nothing needs_review flag on the whole record.
    extraction_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    link_history: Mapped[list["PosterLinkHistory"]] = relationship(
        back_populates="poster", cascade="all, delete-orphan", order_by="PosterLinkHistory.changed_at"
    )


class PosterLinkHistory(Base):
    """Preserves every previous Dropbox link a poster record has had -
    written whenever `dropbox_url` changes via PATCH /api/posters/{id}, so
    "the link changed" is never silently lossy."""

    __tablename__ = "poster_link_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    poster_id: Mapped[str] = mapped_column(ForeignKey("posters.id"), index=True)
    old_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    new_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    poster: Mapped[Poster] = relationship(back_populates="link_history")


class Folder(Base):
    """A single folder in a nested hierarchy of unlimited depth. Deliberately
    resource-agnostic - this table has no idea Posters (or, later,
    Documents) exist; a resource opts in by carrying its own nullable
    `folder_id` column (see Poster.folder_id above). See
    app/folders/service.py for the create/rename/move/delete engine built
    against this table, and app/folders/registry.py for how a resource
    model plugs in for item-counting/deletion-safety purposes.

    `path` is a materialized path of ancestor ids (this folder's own id
    included), "/"-joined root-to-self, e.g. "root_id/year_id/month_id".
    This makes both breadcrumb reconstruction (split on "/", one lookup)
    and subtree queries (`path LIKE '{this.path}/%'` for every descendant)
    single indexed queries instead of a recursive CTE - important since
    "find every poster under this folder or any of its descendants" needs
    to stay fast as the tree grows.
    """

    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("folders.id"), nullable=True, index=True)
    path: Mapped[str] = mapped_column(String(2048), index=True)
    depth: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class StarredItem(Base):
    """Per-user "favorite" flag on any resource, kept as a small side table
    (rather than a `is_starred` column on every resource) so favoriting is
    one reusable feature rather than a column this project would otherwise
    need to re-add on Poster, then Document, then every future resource."""

    __tablename__ = "starred_items"
    __table_args__ = (
        UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_starred_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32), index=True)
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExportJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(Base):
    """Tracks a background ZIP export (see app/storage/archive_zip.py and
    the POST /api/posters/export/zip route). Small/medium exports are
    streamed back synchronously; anything past
    Settings.zip_export_sync_threshold is handed to a background task and
    tracked here instead, so a large "export the entire archive" request
    can't tie up an HTTP worker for minutes. `resource_type` is stored (not
    assumed to always be "poster") so this same table backs Document
    exports later without a schema change."""

    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resource_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[ExportJobStatus] = mapped_column(
        SAEnum(ExportJobStatus), default=ExportJobStatus.PENDING, index=True
    )
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    included_items: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApplicationStatus(str, enum.Enum):
    """Housing Estate Application wizard lifecycle - one status per active
    step (see app/applications/steps.py for the step<->status mapping and
    the forward/backward transition rules), plus two terminal states.
    `current_step` (1-6) is the source of truth for wizard position;
    `status` is the human-facing state that also captures "this step
    failed" and "the whole application is done", which a bare step number
    can't express on its own."""

    DRAFT = "draft"
    EDITING_LETTER = "editing_letter"
    REPLACING_IMAGES = "replacing_images"
    GENERATING = "generating"
    QUALITY_CHECK = "quality_check"
    READY = "ready"
    EXPORTED = "exported"
    FAILED = "failed"


class Application(Base):
    """The parent object for the Housing Estate Application wizard - see
    docs/ARCHITECTURE_REVIEW_2026-07.md and the approved implementation
    plan for the full spec. Everything the 6-step wizard touches (the
    source Poster, the uploaded application PDF, the AI-edited/
    image-replaced generated PDF, the Dropbox asset links, AI call logs,
    step history, quality-check results, and the final export package)
    hangs off one row here, so the wizard is "one Application, one
    resumable record" rather than a set of unrelated pages a user has to
    stitch together themselves.

    Deliberately separate from Poster/ExportJob rather than bolted onto
    either: a Poster is a single archived record (this wizard optionally
    *references* one as its Step 1 output, via `poster_id`), and ExportJob
    tracks one background ZIP build, not a whole multi-step, resumable,
    audited process with its own review/approval concept.
    """

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(ApplicationStatus), default=ApplicationStatus.DRAFT, index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=1, index=True)

    # Step 1 output - the archived poster record this application is for.
    # Nullable because an application starts before a poster is necessarily
    # attached (the wizard's very first screen).
    poster_id: Mapped[str | None] = mapped_column(ForeignKey("posters.id"), nullable=True, index=True)

    # Step 2: the uploaded Housing Estate Application PDF, and the
    # AI-edited/image-replaced result that becomes the final submission.
    application_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    generated_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    template_used: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Step 3: pasted Dropbox shared links, keyed by detected image "role"
    # (e.g. a politician-combination naming pattern) rather than a folder
    # listing - see app/storage/providers/dropbox.py's documented scope
    # (shared-link download/verify only, no OAuth/folder-browsing API).
    dropbox_folder_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_links: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Step 4/AI review: every AI call this application has triggered
    # (provider, operation, prompt summary, duration, success) - a
    # per-application companion to the global AIUsageLog, kept here too so
    # one application's full AI history is visible without cross-
    # referencing another table by timestamp/actor.
    ai_logs: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Full audit trail: one entry per step transition/action
    # ({"step": int, "status": str, "actor": str|None, "at": iso str,
    # "detail": str|None}) - same shape convention as Poster.workflow_steps,
    # append-only, never rewritten.
    step_history: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Step 5 output.
    quality_check_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Step 6 output - path to the assembled submission package (see the
    # approved spec's Export Package structure).
    export_package_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    started_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MetadataExtractionCache(Base):
    """Caches the AI fallback's result for a given block of source text
    (see app/posters/ai_fallback.py) so the same text is never sent to an
    AI provider twice - keyed by a sha256 hash of the exact text rather
    than an autogenerated id, since the natural key here already *is* the
    input, and `db.get(MetadataExtractionCache, text_hash)` is then a
    single indexed lookup with no separate query needed."""

    __tablename__ = "metadata_extraction_cache"

    text_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class LearnedFieldCorrection(Base):
    """A staff-made correction the parser remembers for next time - see
    app/posters/corrections.py. `key_type`/`key_value` name the anchor a
    future parse can recognise again (today, always `key_type="estate_name"`,
    `key_value=<the estate name the parser already resolved correctly>`,
    since that's the concrete, well-defined gap this exists for: the
    estate resolves but its district doesn't, staff correct the district
    once, and every future record mentioning that same estate name gets
    the district filled in automatically from then on). Deliberately
    generic (`field`/`value` are plain strings, not restricted to
    district) so the same table can grow to cover other learned
    corrections (poster_type, etc.) without a schema change.
    """

    __tablename__ = "learned_field_corrections"
    __table_args__ = (
        UniqueConstraint("key_type", "key_value", "field", name="uq_learned_correction_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key_type: Mapped[str] = mapped_column(String(32), index=True)
    key_value: Mapped[str] = mapped_column(String(256), index=True)
    field: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(String(256))
    corrected_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
