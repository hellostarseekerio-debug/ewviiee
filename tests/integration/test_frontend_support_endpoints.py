"""Covers the endpoints added specifically to support the new web frontend:
GET /api/auth/me, admin user list/edit/deactivate/reset-password,
GET /api/documents/{id}/download, and GET /api/dashboard/stats. These
didn't exist before - the frontend's Required Features (User Management,
Dashboard, document download) had nothing to call without them."""
from __future__ import annotations


def test_me_returns_current_user(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert "hashed_password" not in body


def test_admin_can_list_create_edit_deactivate_and_reset_password(bootstrap_admin):
    client, headers = bootstrap_admin

    create = client.post(
        "/api/auth/admin/users",
        json={"username": "staffer", "password": "SuperSecret123!", "role": "viewer"},
        headers=headers,
    )
    assert create.status_code == 201

    listed = client.get("/api/auth/admin/users", headers=headers)
    assert listed.status_code == 200
    usernames = {u["username"] for u in listed.json()}
    assert {"admin", "staffer"} <= usernames

    edited = client.patch(
        "/api/auth/admin/users/staffer", json={"role": "editor", "full_name": "Staff Member"}, headers=headers
    )
    assert edited.status_code == 200
    assert edited.json()["role"] == "editor"
    assert edited.json()["full_name"] == "Staff Member"

    reset = client.post(
        "/api/auth/admin/users/staffer/reset-password",
        json={"new_password": "AnotherSecret456!"},
        headers=headers,
    )
    assert reset.status_code == 200

    login_with_new_password = client.post(
        "/api/auth/token", data={"username": "staffer", "password": "AnotherSecret456!"}
    )
    assert login_with_new_password.status_code == 200

    deactivated = client.delete("/api/auth/admin/users/staffer", headers=headers)
    assert deactivated.status_code == 204

    login_after_deactivation = client.post(
        "/api/auth/token", data={"username": "staffer", "password": "AnotherSecret456!"}
    )
    assert login_after_deactivation.status_code == 401


def test_admin_cannot_deactivate_or_demote_own_account(bootstrap_admin):
    client, headers = bootstrap_admin

    self_delete = client.delete("/api/auth/admin/users/admin", headers=headers)
    assert self_delete.status_code == 400

    self_demote = client.patch("/api/auth/admin/users/admin", json={"role": "viewer"}, headers=headers)
    assert self_demote.status_code == 400


def test_non_admin_cannot_list_or_edit_users(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "viewer1", "password": "SuperSecret123!", "role": "viewer"},
        headers=headers,
    )
    login = client.post("/api/auth/token", data={"username": "viewer1", "password": "SuperSecret123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/auth/admin/users", headers=viewer_headers).status_code == 403
    assert client.patch("/api/auth/admin/users/admin", json={"role": "viewer"}, headers=viewer_headers).status_code == 403


def test_download_document_returns_file_content(bootstrap_admin, tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.database import session_scope
    from app.core.models import Document

    client, headers = bootstrap_admin
    settings = get_settings()
    settings.local_import_root.mkdir(parents=True, exist_ok=True)
    source_file = settings.local_import_root / "report.pdf"
    source_file.write_bytes(b"%PDF-1.4 fake content")

    with session_scope() as db:
        doc = Document(
            filename="report.pdf",
            source_path=str(source_file),
            status="imported",
        )
        db.add(doc)
        db.flush()
        document_id = doc.id

    response = client.get(f"/api/documents/{document_id}/download", headers=headers)
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake content"


def test_download_missing_document_returns_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/documents/does-not-exist/download", headers=headers)
    assert response.status_code == 404


def test_change_own_password_requires_correct_current_password(bootstrap_admin):
    client, headers = bootstrap_admin

    wrong = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword1!", "new_password": "BrandNewSecret789!"},
        headers=headers,
    )
    assert wrong.status_code == 401

    correct = client.post(
        "/api/auth/change-password",
        json={"current_password": "SuperSecret123!", "new_password": "BrandNewSecret789!"},
        headers=headers,
    )
    assert correct.status_code == 200

    old_login = client.post("/api/auth/token", data={"username": "admin", "password": "SuperSecret123!"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/token", data={"username": "admin", "password": "BrandNewSecret789!"})
    assert new_login.status_code == 200


def test_dashboard_stats_returns_real_counts(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/dashboard/stats", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] >= 1
    assert body["active_users"] >= 1
    assert isinstance(body["documents_by_status"], dict)
    assert isinstance(body["recent_activity"], list)
