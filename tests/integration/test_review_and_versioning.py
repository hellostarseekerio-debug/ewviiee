"""Integration test for the approval workflow and version history/rollback
added in the security & production-readiness pass: run a document through
the real pipeline (persisting to the DB via the shared runner), then
exercise approve/reject and rollback through the HTTP API.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from reportlab.pdfgen import canvas

from app.core.config import get_settings
from app.plugins.manager import PluginManager
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import load_all_workflow_definitions
from app.workflow.runner import allowed_import_roots, run_document_through_workflow


def _make_application_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Application date: {{APPLICATION_DATE}}")
    c.showPage()
    c.save()
    return path


def _run_pipeline_with_seeded_ocr(tmp_path) -> str:
    settings = get_settings()
    settings.local_import_root.mkdir(parents=True, exist_ok=True)
    src = _make_application_pdf(tmp_path / "application.pdf")
    dst = settings.local_import_root / "application.pdf"
    shutil.copy2(src, dst)

    manager = PluginManager()
    manager.discover_and_load()
    plugin = manager.get_plugin("housing_estate_poster")

    def fake_ocr(context):
        context.ocr_text = (
            "觀塘 Kwun Tong 藍田邨 Lam Tin Estate Housing Poster v2 議員: Chan Tai Man"
        )
        context.ocr_confidence = 0.95

    def fake_classify(context):
        context.fields["document_type"] = "application_pdf"

    plugin.stage_ocr = fake_ocr
    plugin.stage_classify = fake_classify

    definitions = load_all_workflow_definitions(settings.config_dir / "workflows")
    definition = definitions["housing_estate_poster"]
    engine = WorkflowEngine(plugin_registry={"housing_estate_poster": plugin})

    from app.core.database import session_scope

    with session_scope() as session:
        result = run_document_through_workflow(
            db=session,
            engine=engine,
            definition=definition,
            document_path=dst,
            allowed_roots=allowed_import_roots(settings),
            triggered_by="admin",
        )
    assert result.success, result.halt_reason
    return result.document_id


def test_review_approve_and_versioning(tmp_path, bootstrap_admin):
    client, admin_headers = bootstrap_admin
    document_id = _run_pipeline_with_seeded_ocr(tmp_path)

    get_response = client.get(f"/api/documents/{document_id}", headers=admin_headers)
    assert get_response.status_code == 200
    assert get_response.json()["approval_status"] == "pending"

    versions_response = client.get(f"/api/documents/{document_id}/versions", headers=admin_headers)
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1

    approve_response = client.post(
        f"/api/documents/{document_id}/approve", json={"notes": "Looks correct"}, headers=admin_headers
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approval_status"] == "approved"
    assert approve_response.json()["reviewed_by"] == "admin"


def test_rollback_creates_new_version_without_touching_original(tmp_path, bootstrap_admin):
    client, admin_headers = bootstrap_admin
    document_id = _run_pipeline_with_seeded_ocr(tmp_path)

    versions = client.get(f"/api/documents/{document_id}/versions", headers=admin_headers).json()
    original_version_id = versions[0]["id"]
    original_file = Path(versions[0]["file_path"])
    original_checksum_before = original_file.read_bytes()

    rollback_response = client.post(
        f"/api/documents/{document_id}/rollback",
        json={"version_id": original_version_id},
        headers=admin_headers,
    )
    assert rollback_response.status_code == 200
    assert rollback_response.json()["approval_status"] == "pending"

    # Original version's file must be untouched.
    assert original_file.read_bytes() == original_checksum_before

    versions_after = client.get(f"/api/documents/{document_id}/versions", headers=admin_headers).json()
    assert len(versions_after) == 2
    assert versions_after[1]["notes"].startswith("Rollback to version")


def test_soft_delete_hides_document_from_listing(tmp_path, bootstrap_admin):
    client, admin_headers = bootstrap_admin
    document_id = _run_pipeline_with_seeded_ocr(tmp_path)

    delete_response = client.delete(f"/api/documents/{document_id}", headers=admin_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/documents/{document_id}", headers=admin_headers)
    assert get_response.status_code == 404

    listing = client.get("/api/documents", headers=admin_headers).json()
    assert all(doc["id"] != document_id for doc in listing)

    # Version history must be equally hidden once soft-deleted - a document
    # that 404s on GET /api/documents/{id} must not still expose its
    # version history via a side channel.
    versions_response = client.get(f"/api/documents/{document_id}/versions", headers=admin_headers)
    assert versions_response.status_code == 404
