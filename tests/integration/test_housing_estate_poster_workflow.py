"""End-to-end test of the Housing Estate Poster plugin's business logic
(extract -> validate -> apply_rules -> generate -> review -> export -> archive).

OCR/AI calls are intentionally bypassed here (by seeding `ocr_text` directly)
since PaddleOCR/Tesseract/cloud AI SDKs are optional heavy dependencies not
installed in the base test environment. `tests/unit/test_rule_engine.py`
covers the alias-resolution logic those stages rely on, and
`app/ocr/engine.py` has its own unit coverage boundary via the OCRBackend
protocol.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.pdfgen import canvas

from app.core.config import get_settings
from app.plugins.housing_estate_poster.plugin import HousingEstatePosterPlugin
from app.rules.engine import RuleEngine, load_ruleset
from app.workflow.loader import load_workflow_definition
from app.workflow.models import WorkflowContext


def _make_application_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Application date: {{APPLICATION_DATE}}")
    c.drawString(72, 700, "Footer date: {{FOOTER_DATE}}")
    c.showPage()
    c.save()
    return path


def _build_plugin() -> HousingEstatePosterPlugin:
    settings = get_settings()
    ruleset = load_ruleset(settings.config_dir)
    rule_engine = RuleEngine(ruleset)
    plugin = HousingEstatePosterPlugin()
    plugin.initialize(settings, rule_engine)
    return plugin


def test_full_pipeline_produces_validated_export_and_archive(tmp_path):
    settings = get_settings()
    application_pdf = _make_application_pdf(tmp_path / "application.pdf")
    workflow = load_workflow_definition(
        Path(settings.config_dir) / "workflows" / "housing_estate_poster.yaml"
    )

    plugin = _build_plugin()
    context = WorkflowContext(
        document_path=application_pdf, workflow=workflow, document_id="test-doc-1"
    )

    # Seed fields as if import/classify/ocr already ran.
    context.fields["document_type"] = "application_pdf"
    context.ocr_text = (
        "觀塘 Kwun Tong 藍田邨 Lam Tin Estate\n"
        "Housing Poster v2\n"
        "議員: Chan Tai Man"
    )

    plugin.stage_extract(context)
    assert context.fields["district"] == "Kwun Tong"
    assert context.fields["estate"] == "Lam Tin Estate"
    assert context.fields["politician"] == "Chan Tai Man"
    assert context.fields["version"] == "2"

    plugin.stage_validate(context)  # must not raise
    assert context.validation_errors == []

    plugin.stage_apply_rules(context)
    assert context.fields["output_name"].startswith("Kwun Tong_Lam Tin Estate_2_")
    assert context.fields["output_folder"] == "HousingEstatePosters"

    plugin.stage_generate(context)
    assert context.output_path is not None
    assert context.output_path.exists()

    plugin.stage_review(context)  # manual review disabled in config, must not raise

    plugin.stage_export(context)
    export_path = Path(context.fields["export_path"])
    assert export_path.exists()
    assert export_path.parent.name == "HousingEstatePosters"

    plugin.stage_archive(context)
    assert context.archive_path is not None
    assert context.archive_path.exists()

    plugin.stage_log(context)  # must not raise


def test_pipeline_halts_when_required_fields_missing(tmp_path):
    from app.workflow.engine import WorkflowStageError

    application_pdf = _make_application_pdf(tmp_path / "application.pdf")
    settings = get_settings()
    workflow = load_workflow_definition(
        Path(settings.config_dir) / "workflows" / "housing_estate_poster.yaml"
    )
    plugin = _build_plugin()
    context = WorkflowContext(document_path=application_pdf, workflow=workflow, document_id="test-doc-2")
    context.fields["document_type"] = "application_pdf"
    context.ocr_text = "unrelated text with no district or estate"

    plugin.stage_extract(context)

    try:
        plugin.stage_validate(context)
        assert False, "expected WorkflowStageError"
    except WorkflowStageError as exc:
        assert "district" in str(exc) or "estate" in str(exc)
