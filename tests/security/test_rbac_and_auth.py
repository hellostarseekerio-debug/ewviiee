"""Security tests: authentication requirement, RBAC enforcement, privilege
escalation prevention, path traversal rejection, malicious upload rejection.
"""
from __future__ import annotations


def test_unauthenticated_requests_are_rejected(api_client):
    assert api_client.get("/api/documents").status_code == 401
    assert api_client.get("/api/search").status_code == 401
    assert api_client.get("/api/workflows").status_code == 401
    assert (
        api_client.post("/api/workflows/run", json={"workflow_name": "x", "document_paths": ["a"]}).status_code
        == 401
    )


def test_bootstrap_admin_then_second_bootstrap_is_blocked(api_client):
    first = api_client.post(
        "/api/auth/users", json={"username": "admin", "password": "SuperSecret123!", "role": "admin"}
    )
    assert first.status_code == 201
    assert first.json()["role"] == "admin"

    second = api_client.post(
        "/api/auth/users", json={"username": "eve", "password": "AnotherPass123!", "role": "admin"}
    )
    assert second.status_code == 403


def test_weak_password_rejected_on_bootstrap(api_client):
    response = api_client.post(
        "/api/auth/users", json={"username": "admin", "password": "weak", "role": "admin"}
    )
    assert response.status_code == 422


def test_admin_create_user_requires_authentication(api_client):
    response = api_client.post(
        "/api/auth/admin/users",
        json={"username": "someone", "password": "SomePass123!", "role": "viewer"},
    )
    assert response.status_code == 401


def test_viewer_cannot_run_workflows(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "viewer1", "password": "ViewerPass123!", "role": "viewer"},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": "viewer1", "password": "ViewerPass123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/workflows/run",
        json={"workflow_name": "housing_estate_poster", "document_paths": ["/etc/passwd"]},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_editor_path_traversal_attempt_is_rejected_not_a_crash(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "editor1", "password": "EditorPass123!", "role": "editor"},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": "editor1", "password": "EditorPass123!"})
    editor_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/api/workflows/run",
        json={"workflow_name": "housing_estate_poster", "document_paths": ["/etc/passwd"]},
        headers=editor_headers,
    )
    assert response.status_code == 200  # request succeeds, the individual document fails safely
    body = response.json()
    assert body["succeeded"] == 0
    assert body["failed"] == 1
    assert "outside all permitted import roots" in body["results"][0]["halt_reason"]


def test_malicious_upload_rejected_by_signature_check(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    response = client.post(
        "/api/documents/upload",
        files={"file": ("malware.pdf", b"MZ\x90\x00fake-exe-content", "application/pdf")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"]


def test_legitimate_upload_is_accepted(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    content = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    response = client.post(
        "/api/documents/upload",
        files={"file": ("poster.png", content, "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["stored_path"].endswith(".png")


def test_disallowed_extension_rejected(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    response = client.post(
        "/api/documents/upload",
        files={"file": ("script.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_oversized_upload_rejected(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    from app.core.config import get_settings

    too_big = b"%PDF-" + b"0" * (get_settings().max_upload_size_bytes + 1)
    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.pdf", too_big, "application/pdf")},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_pagination_limit_is_clamped(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    response = client.get("/api/documents?limit=999999", headers=admin_headers)
    assert response.status_code == 422  # exceeds the le=200 constraint
