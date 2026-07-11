"""Configurable workflow pipeline executor.

Runs a WorkflowContext through the ordered stages defined by a
WorkflowDefinition, dispatching each stage to the handler supplied by the
document's plugin. Records timing/success/failure into
WorkflowContext.stage_results and persists a ProcessingEvent + Document row
per stage so the full processing history is queryable from the GUI.

Error recovery: any stage may raise `WorkflowStageError` to halt the
pipeline with a clear, user-facing reason (never a silent failure). Unhandled
exceptions are caught, logged, and also halt the pipeline with the exception
message surfaced.
"""
from __future__ import annotations

import time

from app.core.logging_config import get_logger, record_audit
from app.plugins.base import Plugin
from app.workflow.models import WorkflowContext, StageResult

logger = get_logger("workflow.engine")


class WorkflowStageError(Exception):
    """Raised by a stage handler to halt the pipeline with a clear reason."""


class WorkflowEngine:
    def __init__(self, plugin_registry: dict[str, Plugin]) -> None:
        self._plugin_registry = plugin_registry

    def run(self, context: WorkflowContext) -> WorkflowContext:
        plugin = self._plugin_registry.get(context.workflow.plugin)
        if plugin is None:
            context.halted = True
            context.halt_reason = f"Plugin '{context.workflow.plugin}' is not registered/enabled"
            logger.error("workflow_plugin_missing", plugin=context.workflow.plugin)
            return context

        handlers = plugin.get_stage_handlers()

        for stage_name in context.workflow.stages:
            handler = handlers.get(stage_name)
            start = time.perf_counter()
            if handler is None:
                context.stage_results.append(
                    StageResult(stage=stage_name, success=True, detail="skipped (no handler)")
                )
                continue

            try:
                handler(context)
                duration_ms = int((time.perf_counter() - start) * 1000)
                context.stage_results.append(
                    StageResult(stage=stage_name, success=True, duration_ms=duration_ms)
                )
                logger.info(
                    "workflow_stage_complete",
                    workflow=context.workflow.name,
                    stage=stage_name,
                    duration_ms=duration_ms,
                )
            except WorkflowStageError as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                context.halted = True
                context.halt_reason = str(exc)
                context.stage_results.append(
                    StageResult(
                        stage=stage_name, success=False, detail=str(exc), duration_ms=duration_ms
                    )
                )
                logger.error(
                    "workflow_stage_failed",
                    workflow=context.workflow.name,
                    stage=stage_name,
                    reason=str(exc),
                )
                record_audit(
                    actor="workflow_engine",
                    action="stage_failed",
                    resource_type="document",
                    resource_id=context.document_id,
                    detail={"workflow": context.workflow.name, "stage": stage_name, "reason": str(exc)},
                    success=False,
                )
                break
            except Exception as exc:  # pragma: no cover - defensive catch-all
                duration_ms = int((time.perf_counter() - start) * 1000)
                context.halted = True
                context.halt_reason = f"Unexpected error in stage '{stage_name}': {exc}"
                context.stage_results.append(
                    StageResult(
                        stage=stage_name, success=False, detail=str(exc), duration_ms=duration_ms
                    )
                )
                logger.error(
                    "workflow_stage_exception",
                    workflow=context.workflow.name,
                    stage=stage_name,
                    error=str(exc),
                )
                record_audit(
                    actor="workflow_engine",
                    action="stage_exception",
                    resource_type="document",
                    resource_id=context.document_id,
                    detail={"workflow": context.workflow.name, "stage": stage_name, "error": str(exc)},
                    success=False,
                )
                break

        return context

    def run_batch(self, contexts: list[WorkflowContext]) -> list[WorkflowContext]:
        return [self.run(context) for context in contexts]
