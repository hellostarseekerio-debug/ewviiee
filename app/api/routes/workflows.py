"""Workflow execution endpoints - runs one or more documents through a
configured workflow using the plugin/rule/workflow engines, and persists the
resulting Document + ProcessingEvent rows for search/audit/reporting."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workflow_engine
from app.api.schemas import WorkflowRunRequest, WorkflowRunResponse, WorkflowRunResult
from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import Document, DocumentStatus, ProcessingEvent
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import load_all_workflow_definitions

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("")
def list_workflows(_=Depends(get_current_user)):
    settings = get_settings()
    definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
    return [
        {"name": d.name, "display_name": d.display_name, "plugin": d.plugin, "stages": d.stages}
        for d in definitions.values()
    ]


@router.post("/run", response_model=WorkflowRunResponse)
def run_workflow(
    payload: WorkflowRunRequest,
    db: Session = Depends(get_db),
    engine: WorkflowEngine = Depends(get_workflow_engine),
    _=Depends(get_current_user),
):
    settings = get_settings()
    definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
    definition = definitions.get(payload.workflow_name)
    if definition is None:
        raise HTTPException(404, f"Unknown workflow: {payload.workflow_name}")

    from app.workflow.models import WorkflowContext

    results: list[WorkflowRunResult] = []
    succeeded = 0
    failed = 0

    for doc_path_str in payload.document_paths:
        doc_path = Path(doc_path_str)
        document_id = str(uuid.uuid4())
        context = WorkflowContext(document_path=doc_path, workflow=definition, document_id=document_id)
        context = engine.run(context)

        document = Document(
            id=document_id,
            filename=doc_path.name,
            source_path=str(doc_path),
            document_type=context.fields.get("document_type"),
            workflow_name=definition.name,
            status=DocumentStatus.FAILED if context.halted else DocumentStatus.ARCHIVED,
            district=context.fields.get("district"),
            estate=context.fields.get("estate"),
            title=context.fields.get("title"),
            politician=context.fields.get("politician"),
            version=context.fields.get("version"),
            source=context.fields.get("source"),
            ocr_text=context.ocr_text,
            ai_confidence=context.ai_confidence,
            ocr_confidence=context.ocr_confidence,
            extracted_fields=context.fields,
            output_path=str(context.output_path) if context.output_path else None,
            archive_path=str(context.archive_path) if context.archive_path else None,
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
        db.commit()

        if context.halted:
            failed += 1
        else:
            succeeded += 1

        results.append(
            WorkflowRunResult(
                document_path=str(doc_path),
                success=not context.halted,
                halt_reason=context.halt_reason or None,
                output_path=str(context.output_path) if context.output_path else None,
                fields=context.fields,
            )
        )

    return WorkflowRunResponse(
        workflow_name=definition.name,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
