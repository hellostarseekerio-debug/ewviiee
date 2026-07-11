"""Workflow execution endpoints - runs one or more documents through a
configured workflow using the plugin/rule/workflow engines, and persists the
resulting Document + ProcessingEvent + DocumentVersion rows for
search/audit/reporting via the shared `app.workflow.runner` service.

Security: only Editor+ may trigger a run (Viewers/Reviewers are read-only).
Every `document_paths` entry is resolved and verified to fall under an
approved import/archive/export root before it is ever opened - this is the
platform's path-traversal guard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_current_user, get_workflow_engine, require_role
from app.api.rate_limit import limiter
from app.api.schemas import WorkflowRunRequest, WorkflowRunResponse, WorkflowRunResult
from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import UserRole
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import load_all_workflow_definitions
from app.workflow.runner import allowed_import_roots, run_batch_through_workflow

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
@limiter.limit(lambda: get_settings().rate_limit_default)
def run_workflow(
    request: Request,
    payload: WorkflowRunRequest,
    db=Depends(get_db),
    engine: WorkflowEngine = Depends(get_workflow_engine),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    settings = get_settings()
    definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
    definition = definitions.get(payload.workflow_name)
    if definition is None:
        raise HTTPException(404, f"Unknown workflow: {payload.workflow_name}")

    run_results = run_batch_through_workflow(
        db=db,
        engine=engine,
        definition=definition,
        document_paths=payload.document_paths,
        allowed_roots=allowed_import_roots(settings),
        triggered_by=payload.triggered_by or current_user.username,
    )

    results = [
        WorkflowRunResult(
            document_path=r.document_path,
            success=r.success,
            halt_reason=r.halt_reason,
            output_path=r.output_path,
            fields=r.fields,
        )
        for r in run_results
    ]
    succeeded = sum(1 for r in run_results if r.success)

    return WorkflowRunResponse(
        workflow_name=definition.name,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )
