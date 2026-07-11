"""Pydantic request/response models for the API layer."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    total: int
    results: list[DocumentOut]


class WorkflowRunRequest(BaseModel):
    workflow_name: str
    document_paths: list[str]
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
    access_token: str
    token_type: str = "bearer"


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str | None = None
    role: str = "viewer"
