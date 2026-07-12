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
