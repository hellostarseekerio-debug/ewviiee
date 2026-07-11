from __future__ import annotations



from app.workflow.engine import WorkflowEngine, WorkflowStageError
from app.workflow.models import WorkflowContext, WorkflowDefinition


class _FakePlugin:
    plugin_id = "fake"
    display_name = "Fake"
    version = "0.0.1"

    def __init__(self, fail_at: str | None = None) -> None:
        self._fail_at = fail_at
        self.calls: list[str] = []

    def get_stage_handlers(self):
        def make_handler(stage: str):
            def handler(context: WorkflowContext) -> None:
                self.calls.append(stage)
                if stage == self._fail_at:
                    raise WorkflowStageError(f"{stage} deliberately failed")
                context.fields[stage] = "done"

            return handler

        return {stage: make_handler(stage) for stage in ["import", "classify", "validate"]}


def _definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test_workflow",
        display_name="Test Workflow",
        plugin="fake",
        stages=["import", "classify", "validate"],
    )


def test_workflow_runs_all_stages_successfully(tmp_path):
    plugin = _FakePlugin()
    engine = WorkflowEngine(plugin_registry={"fake": plugin})
    context = WorkflowContext(document_path=tmp_path / "doc.pdf", workflow=_definition())

    result = engine.run(context)

    assert not result.halted
    assert plugin.calls == ["import", "classify", "validate"]
    assert all(sr.success for sr in result.stage_results)


def test_workflow_halts_on_stage_error(tmp_path):
    plugin = _FakePlugin(fail_at="classify")
    engine = WorkflowEngine(plugin_registry={"fake": plugin})
    context = WorkflowContext(document_path=tmp_path / "doc.pdf", workflow=_definition())

    result = engine.run(context)

    assert result.halted
    assert "classify deliberately failed" in result.halt_reason
    # validate stage must never run once classify halted the pipeline
    assert plugin.calls == ["import", "classify"]


def test_workflow_reports_missing_plugin(tmp_path):
    engine = WorkflowEngine(plugin_registry={})
    context = WorkflowContext(document_path=tmp_path / "doc.pdf", workflow=_definition())

    result = engine.run(context)

    assert result.halted
    assert "not registered" in result.halt_reason
