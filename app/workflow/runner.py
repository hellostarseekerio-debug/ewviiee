"""Shared workflow execution service.

Both the FastAPI `/api/workflows/run` endpoint and the PySide6 desktop GUI
need to: run a document through a `WorkflowEngine`, persist the resulting
`Document` + `ProcessingEvent` rows, record a new `DocumentVersion` for any
generated output (never overwriting the original source file), and write an
audit log entry. That logic lives here once so both call sites stay in sync
rather than duplicating (and inevitably diverging) the persistence rules.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.file_safety import UnsafeFileError, resolve_within_root
from app.core.logging_config import get_logger, record_audit
from app.core.models import ApprovalStatus, Document, DocumentStatus, DocumentVersion, ProcessingEvent
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowContext, WorkflowDefinition

logger = get_logger("workflow.runner")


@dataclass
class DocumentRunResult:
    document_path: str
    document_id: str
    success: bool
    halt_reason: str | None
    output_path: str | None
    fields: dict


def _json_safe(value):
    """Recursively converts values that the JSON column can't serialize
    (datetime/date, Path) into strings. Workflow/plugin `fields` dicts are
    free-form by design (any plugin can add any key), so this boundary must
    not assume every value is already JSON-safe."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def allowed_import_roots(settings) -> list[Path]:
    """Every root a document path is permitted to come from. Rejecting
    anything outside these roots is the platform's path-traversal guard for
    workflow execution - a client can never point the engine at an arbitrary
    server-side file."""
    roots = [settings.local_import_root, settings.archive_root, settings.export_root]
    for optional_root in (settings.dropbox_root, settings.google_drive_root, settings.onedrive_root):
        if optional_root:
            roots.append(optional_root)
    return roots


def run_document_through_workflow(
    *,
    db: Session,
    engine: WorkflowEngine,
    definition: WorkflowDefinition,
    document_path: Path,
    allowed_roots: list[Path],
    triggered_by: str | None,
) -> DocumentRunResult:
    """Validates the path, runs the pipeline, and persists all resulting rows.
    Raises UnsafeFileError if `document_path` escapes `allowed_roots` -
    callers must turn that into an HTTP 400/403 (API) or a visible error
    (GUI), never a silent skip."""
    safe_path = resolve_within_root(document_path, allowed_roots)

    document_id = str(uuid.uuid4())
    context = WorkflowContext(document_path=safe_path, workflow=definition, document_id=document_id)
    context = engine.run(context)

    document = Document(
        id=document_id,
        filename=safe_path.name,
        source_path=str(safe_path),
        document_type=context.fields.get("document_type"),
        workflow_name=definition.name,
        status=DocumentStatus.FAILED if context.halted else DocumentStatus.ARCHIVED,
        district=context.fields.get("district"),
        estate=context.fields.get("estate"),
        title=context.fields.get("title"),
        politician=context.fields.get("politician"),
        version=context.fields.get("version"),
        source=context.fields.get("source"),
        document_date=context.fields.get("date") if isinstance(context.fields.get("date"), datetime) else None,
        ocr_text=context.ocr_text,
        ai_confidence=context.ai_confidence,
        ocr_confidence=context.ocr_confidence,
        extracted_fields=_json_safe(context.fields),
        output_path=str(context.output_path) if context.output_path else None,
        archive_path=str(context.archive_path) if context.archive_path else None,
        approval_status=ApprovalStatus.PENDING,
    )
    db.add(document)

    for stage_result in context.stage_results:
        db.add(
            ProcessingEvent(
                document_id=document_id,
                stage=stage_result.stage,
                status="success" if stage_result.success else "failed",
                detail=stage_result.detail,
                duration_ms=stage_result.duration_ms,
            )
        )

    if context.output_path and context.output_path.exists():
        checksum = hashlib.sha256(context.output_path.read_bytes()).hexdigest()
        db.add(
            DocumentVersion(
                document_id=document_id,
                version_number=1,
                file_path=str(context.output_path),
                checksum_sha256=checksum,
                created_by=triggered_by,
                notes="Initial generation",
            )
        )

    db.commit()

    record_audit(
        actor=triggered_by,
        action="workflow_run",
        resource_type="document",
        resource_id=document_id,
        detail={"workflow": definition.name, "success": not context.halted},
        success=not context.halted,
    )

    return DocumentRunResult(
        document_path=str(safe_path),
        document_id=document_id,
        success=not context.halted,
        halt_reason=context.halt_reason or None,
        output_path=str(context.output_path) if context.output_path else None,
        fields=context.fields,
    )


def run_batch_through_workflow(
    *,
    db: Session,
    engine: WorkflowEngine,
    definition: WorkflowDefinition,
    document_paths: list[str],
    allowed_roots: list[Path],
    triggered_by: str | None,
) -> list[DocumentRunResult]:
    results: list[DocumentRunResult] = []
    for doc_path_str in document_paths:
        try:
            result = run_document_through_workflow(
                db=db,
                engine=engine,
                definition=definition,
                document_path=Path(doc_path_str),
                allowed_roots=allowed_roots,
                triggered_by=triggered_by,
            )
        except UnsafeFileError as exc:
            logger.warning("workflow_run_rejected_path", path=doc_path_str, reason=str(exc))
            record_audit(
                actor=triggered_by,
                action="workflow_run_rejected_path",
                detail={"path": doc_path_str, "reason": str(exc)},
                success=False,
            )
            result = DocumentRunResult(
                document_path=doc_path_str,
                document_id="",
                success=False,
                halt_reason=str(exc),
                output_path=None,
                fields={},
            )
        results.append(result)
    return results
