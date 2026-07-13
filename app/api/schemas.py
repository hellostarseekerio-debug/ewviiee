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
    estate: str | None
    poster_title: str | None
    poster_type: str | None
    route_number: str | None
    document_date: datetime | None
    dropbox_url: str | None
    language: str | None
    keywords: list[str] | None
    notes: str | None
    workflow_steps: list[WorkflowStep] | None
    approval_status: str
    status: str
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
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    document_date: datetime | None = None
    dropbox_url: str | None = None
    language: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    workflow_steps: list[WorkflowStep] | None = None

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
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    document_date: datetime | None = None
    dropbox_url: str | None = None
    language: str | None = None
    keywords: list[str] | None = None
    notes: str | None = None
    workflow_steps: list[WorkflowStep] | None = None
    approval_status: str | None = None

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
