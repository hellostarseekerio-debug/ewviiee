from __future__ import annotations

from app.core.friendly_errors import humanize_error


def test_connection_refused_gets_friendly_message():
    result = humanize_error("[Errno 111] Connection refused")
    assert "network connection" in result.lower()
    assert "Connection refused" in result  # technical detail preserved


def test_file_not_found_gets_friendly_message():
    result = humanize_error("FileNotFoundError: [Errno 2] No such file or directory: 'x.pdf'")
    assert "could not be found" in result.lower()


def test_permission_denied_gets_friendly_message():
    result = humanize_error("PermissionError: [Errno 13] Permission denied: '/data/x.pdf'")
    assert "permission" in result.lower()


def test_disk_full_gets_friendly_message():
    result = humanize_error("OSError: [Errno 28] No space left on device")
    assert "storage space" in result.lower()


def test_unrecognized_error_gets_generic_fallback_with_detail():
    result = humanize_error("SomeWeirdInternalError: flux capacitor misaligned")
    assert "flux capacitor misaligned" in result
    assert "Something went wrong" in result


def test_empty_message_does_not_crash():
    result = humanize_error("")
    assert "unknown error" in result.lower()


def test_workflow_engine_humanizes_unexpected_exceptions():
    """An unhandled exception from a stage handler must reach the user as
    plain language, not a raw Python traceback fragment."""
    from app.workflow.engine import WorkflowEngine
    from app.workflow.models import WorkflowContext, WorkflowDefinition

    class _BrokenPlugin:
        plugin_id = "broken"
        display_name = "Broken"
        version = "0.0.1"

        def get_stage_handlers(self):
            def handler(context):
                raise ConnectionError("Connection refused")

            return {"import": handler}

    definition = WorkflowDefinition(
        name="broken_workflow", display_name="Broken", plugin="broken", stages=["import"]
    )
    engine = WorkflowEngine(plugin_registry={"broken": _BrokenPlugin()})
    context = WorkflowContext(document_path=__import__("pathlib").Path("/tmp/x.pdf"), workflow=definition)

    result = engine.run(context)

    assert result.halted
    assert "Connection refused" not in result.halt_reason.split("Technical detail:")[0]
    assert "network connection" in result.halt_reason.lower()
    assert "Connection refused" in result.halt_reason  # still present, just after the friendly part
