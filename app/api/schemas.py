"""Pydantic request/response models for the API layer."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DocumentOut(BaseModel):
    id: str
    filename: str
    document_type: str | None
    workflow_name: str | None
    status: str
    district: str | None
    estate: str | None
    title: str | None
    politician: str | None
    reference_number: str | None
    document_date: datetime | None
    language: str | None
    version: str | None
    ai_confidence: float | None
    ocr_confidence: float | None
    approval_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersionOut(BaseModel):
    id: str
    version_number: int
    file_path: str
    checksum_sha256: str | None
    created_by: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    total: int
    results: list[DocumentOut]


class WorkflowRunRequest(BaseModel):
    workflow_name: str
    document_paths: list[str] = Field(..., min_length=1, max_length=500)
    triggered_by: str | None = None


class WorkflowRunResult(BaseModel):
    document_path: str
    success: bool
    halt_reason: str | None
    output_path: str | None
    fields: dict


class WorkflowRunResponse(BaseModel):
    workflow_name: str
    total: int
    succeeded: int
    failed: int
    results: list[WorkflowRunResult]


class PluginOut(BaseModel):
    plugin_id: str
    display_name: str
    version: str


class TokenResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    pending_token: str | None = None
    # Included on a successful login so the frontend doesn't need a
    # second round trip to GET /api/auth/me just to learn who logged in -
    # see the login-latency profiling that motivated this (login used to
    # sequentially await token issuance *then* a separate /me call before
    # the UI could navigate anywhere).
    user: UserOut | None = None


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    recovery_codes: list[str]


class MFAConfirmRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class MFAVerifyRequest(BaseModel):
    pending_token: str
    code: str


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str
    full_name: str | None = None
    role: str = "viewer"

    @field_validator("username")
    @classmethod
    def username_must_be_safe(cls, value: str) -> str:
        if not value.replace("_", "").replace(".", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, '.', '_', '-'")
        return value


class ReviewDecisionRequest(BaseModel):
    notes: str | None = None


class RollbackRequest(BaseModel):
    version_id: str


class SystemSettingUpdateRequest(BaseModel):
    key: str
    value: str


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str


class DashboardStats(BaseModel):
    total_documents: int
    documents_by_status: dict[str, int]
    documents_by_approval_status: dict[str, int]
    total_users: int
    active_users: int
    ai_usage_total: int
    ai_usage_cloud: int
    ai_usage_local: int
    recent_activity: list[dict]

    # --- Phase 2B additions --------------------------------------------------
    total_posters: int
    posters_by_district: dict[str, int]
    posters_by_estate: dict[str, int]
    posters_by_status: dict[str, int]
    recent_poster_uploads: list[dict]
    broken_dropbox_links: int
    duplicate_poster_groups: int
    downloads_today: int
    pending_reviews: int
    most_active_users: list[dict]
    export_storage_bytes: int


# --- Poster Archive (app/posters/parser.py, app/api/routes/posters.py) -----

class WorkflowStep(BaseModel):
    """One structured step of a poster's optional workflow instructions,
    e.g. {"step": 1, "action": "Generate application PDF"} - stored as
    data (see Poster.workflow_steps) rather than a plain-text blob so a
    future automation stage can read/execute it without re-parsing text."""

    step: int = Field(..., ge=1)
    action: str = Field(..., min_length=1, max_length=256)
    detail: str | None = Field(default=None, max_length=2000)


class PosterOut(BaseModel):
    id: str
    district: str | None
    region: str | None
    estate: str | None
    poster_title: str | None
    poster_type: str | None
    route_number: str | None
    politicians: list[str] | None
    document_date: datetime | None
    date_to: datetime | None
    dropbox_url: str | None
    language: str | None
    keywords: list[str] | None
    notes: str | None
    source_text: str | None
    workflow_steps: list[WorkflowStep] | None
    approval_status: str
    status: str
    folder_id: str | None
    campaign_name: str | None
    government_department: str | None
    version: str | None
    source: str | None
    needs_review: bool
    dropbox_link_broken: bool | None
    dropbox_last_verified_at: datetime | None
    extraction_confidence: dict[str, float] | None
    extraction_sources: dict[str, str] | None
    ai_summary: str | None
    ocr_text: str | None
    attachments: list[dict] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PosterListResponse(BaseModel):
    total: int
    results: list[PosterOut]


class PosterCreateRequest(BaseModel):
    """Manual single-record creation - the paste-text import path
    (POST /api/posters/import) is the primary way records are added, but a
    manual add covers the case of a single record typed in directly."""

    district: str | None = None
    region: str | None = None
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    politicians: list[str] | None = None
    document_date: datetime | None = None
    date_to: datetime | None = None
    dropbox_url: str | None = None
    language: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    workflow_steps: list[WorkflowStep] | None = None
    campaign_name: str | None = None
    government_department: str | None = None
    version: str | None = None
    # Explicit destination overrides the Year/Month/District/Estate/Poster-
    # Type auto-suggestion (app/folders/suggestions.py) - omit to let the
    # system file it automatically based on district/estate/poster_type/
    # document_date.
    folder_id: str | None = None

    @field_validator("dropbox_url")
    @classmethod
    def dropbox_url_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.posters.validation import assert_valid_dropbox_url

        assert_valid_dropbox_url(value)
        return value.strip()


class PosterUpdateRequest(BaseModel):
    district: str | None = None
    region: str | None = None
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    politicians: list[str] | None = None
    document_date: datetime | None = None
    date_to: datetime | None = None
    dropbox_url: str | None = None
    language: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    workflow_steps: list[WorkflowStep] | None = None
    approval_status: str | None = None
    campaign_name: str | None = None
    government_department: str | None = None
    version: str | None = None
    # Lets an Editor manually clear the parser's low-confidence flag once
    # they've confirmed the record is fine (or re-flag it themselves).
    needs_review: bool | None = None
    folder_id: str | None = None

    @field_validator("dropbox_url")
    @classmethod
    def dropbox_url_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.posters.validation import assert_valid_dropbox_url

        assert_valid_dropbox_url(value)
        return value.strip()


class PosterStatusChangeRequest(BaseModel):
    """Moves a poster through its status lifecycle (see
    app/posters/status.py for the allowed-transition graph). Deliberately a
    dedicated endpoint rather than folded into PATCH /api/posters/{id} -
    the transition graph and role requirements need to be enforced
    consistently, which a generic field-by-field update can't do safely."""

    status: str
    notes: str | None = Field(default=None, max_length=2000)
    force: bool = False


class PosterImportRequest(BaseModel):
    text: str = Field(..., min_length=1)
    # Applies to every record in this paste, overriding the per-record
    # Year/Month/District/Estate auto-suggestion - e.g. "file this whole
    # batch under a folder I already picked" instead of auto-filing each
    # one by its own parsed district/estate/date.
    folder_id: str | None = None


class PosterImportResult(BaseModel):
    dropbox_url: str
    status: str  # "imported" | "duplicate" | "invalid_url"
    id: str | None = None
    reason: str | None = None


class PosterImportResponse(BaseModel):
    total_parsed: int
    imported: int
    duplicates: int
    invalid: int
    results: list[PosterImportResult]


class PosterBulkDeleteRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=1000)


class PosterBulkMoveRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=1000)
    folder_id: str | None = None  # None = move to root (unfiled)


class PosterBulkFieldUpdateRequest(BaseModel):
    """Bulk retag/reclassify - only the fields actually provided are
    changed across every listed record; omitted fields are left alone."""

    ids: list[str] = Field(..., min_length=1, max_length=1000)
    district: str | None = None
    estate: str | None = None
    poster_type: str | None = None
    add_keywords: list[str] | None = None


class PosterBulkStatusRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=1000)
    status: str
    force: bool = False


class DuplicateGroupOut(BaseModel):
    reason: str
    poster_ids: list[str]
    detail: str


class LinkVerifyResultOut(BaseModel):
    poster_id: str
    dropbox_link_broken: bool | None
    dropbox_last_verified_at: datetime | None


class PosterLinkHistoryOut(BaseModel):
    id: str
    old_url: str | None
    new_url: str | None
    changed_by: str | None
    changed_at: datetime

    model_config = {"from_attributes": True}


class PosterReparseResult(BaseModel):
    """One record's outcome from POST /api/posters/reparse - `fields_filled`
    maps each field that was blank and is now populated to the source that
    filled it in (mirrors Poster.extraction_sources: "regex" | "rule_engine"
    | "learned" | "ai" | "default"), so it's visible exactly what changed
    and where the new value came from - never which fields were merely
    re-confirmed, since a value that was already present is left untouched."""

    id: str
    fields_filled: dict[str, str]


class PosterReparseResponse(BaseModel):
    scanned: int
    updated: int
    results: list[PosterReparseResult]


# --- Folders: app/folders/service.py - generic, not poster-specific ------


class FolderOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    path: str
    depth: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FolderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: str | None = None


class FolderRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class FolderMoveRequest(BaseModel):
    parent_id: str | None = None


class FolderStatsOut(BaseModel):
    folder_id: str
    direct_subfolders: int
    direct_items: int
    total_subfolders: int
    total_items: int


class FolderTreeNodeOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    depth: int
    direct_items: int
    total_items: int
    children: list["FolderTreeNodeOut"]


class FolderDetailOut(BaseModel):
    folder: FolderOut
    breadcrumbs: list[FolderOut]
    stats: FolderStatsOut
    children: list[FolderOut]


# --- Starred items (favorites) - reusable across resource types ----------


class StarredItemOut(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StarRequest(BaseModel):
    resource_type: str
    resource_id: str


# --- ZIP export (app/storage/archive_zip.py) ------------------------------


class PosterZipExportRequest(BaseModel):
    """Selects which posters to export - see app/api/routes/posters.py for
    how these are prioritized: `ids` (selected files) takes precedence,
    then `folder_id` (current folder, optionally recursive), then the
    plain filter fields (search results); no fields at all means the
    entire archive."""

    ids: list[str] | None = None
    folder_id: str | None = None
    recursive: bool = True
    q: str | None = None
    district: str | None = None
    poster_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    has_dropbox: bool | None = None


class ExportJobOut(BaseModel):
    id: str
    resource_type: str
    status: str
    requested_by: str | None
    total_items: int
    included_items: int
    file_size_bytes: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ZipExportAcceptedResponse(BaseModel):
    job_id: str
    status: str
    total_items: int


# --- Housing Estate Application wizard (app/applications/) -----------------


class ApplicationStepHistoryEntry(BaseModel):
    step: int
    status: str
    actor: str | None
    at: str
    detail: str | None


class ApplicationAILogEntry(BaseModel):
    step: int
    provider: str
    operation: str
    prompt_summary: str | None
    duration_ms: int | None
    success: bool
    at: str


class ApplicationOut(BaseModel):
    id: str
    status: str
    current_step: int
    poster_id: str | None
    application_pdf_path: str | None
    generated_pdf_path: str | None
    template_used: str | None
    dropbox_folder_url: str | None
    image_links: dict[str, str] | None
    ai_logs: list[ApplicationAILogEntry] | None
    step_history: list[ApplicationStepHistoryEntry] | None
    quality_check_results: dict | None
    export_package_path: str | None
    started_by: str | None
    completed_by: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    total: int
    results: list[ApplicationOut]


class ApplicationAttachPosterRequest(BaseModel):
    poster_id: str = Field(..., min_length=1)
