"""Covers the Housing Estate Application wizard endpoints (slice 1):
create, get, list, and step 1's poster attachment - see
app/api/routes/applications.py and the approved implementation plan."""
from __future__ import annotations


def _create_poster(client, headers, dropbox_url, **extra):
    payload = {"poster_title": "Test", "dropbox_url": dropbox_url, **extra}
    response = client.post("/api/posters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_start_application_creates_a_draft_at_step_one(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/applications", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["current_step"] == 1
    assert body["status"] == "draft"
    assert body["poster_id"] is None
    assert len(body["step_history"]) == 1


def test_start_application_requires_editor_role(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "viewer1", "password": "SuperSecret123!", "role": "viewer"},
        headers=headers,
    )
    login = client.post("/api/auth/token", data={"username": "viewer1", "password": "SuperSecret123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/applications", headers=viewer_headers)
    assert response.status_code == 403


def test_get_application_roundtrips(bootstrap_admin):
    client, headers = bootstrap_admin
    created = client.post("/api/applications", headers=headers).json()

    response = client.get(f"/api/applications/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_nonexistent_application_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/applications/does-not-exist", headers=headers)
    assert response.status_code == 404


def test_list_applications_returns_created_ones(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/applications", headers=headers)
    client.post("/api/applications", headers=headers)

    response = client.get("/api/applications", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    assert len(body["results"]) >= 2


def test_list_applications_filters_by_status(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/applications", headers=headers)

    response = client.get("/api/applications", params={"status": "draft"}, headers=headers)
    assert response.status_code == 200
    assert all(a["status"] == "draft" for a in response.json()["results"])

    response = client.get("/api/applications", params={"status": "exported"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_list_applications_rejects_invalid_status(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/applications", params={"status": "not-a-real-status"}, headers=headers)
    assert response.status_code == 422


def test_attach_poster_advances_application_to_step_two(bootstrap_admin):
    client, headers = bootstrap_admin
    application = client.post("/api/applications", headers=headers).json()
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/app-wizard-1")

    response = client.post(
        f"/api/applications/{application['id']}/step1/attach-poster",
        json={"poster_id": poster["id"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["poster_id"] == poster["id"]
    assert body["current_step"] == 2
    assert body["status"] == "editing_letter"


def test_attach_nonexistent_poster_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    application = client.post("/api/applications", headers=headers).json()

    response = client.post(
        f"/api/applications/{application['id']}/step1/attach-poster",
        json={"poster_id": "does-not-exist"},
        headers=headers,
    )
    assert response.status_code == 404


def test_attach_poster_to_nonexistent_application_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/app-wizard-2")

    response = client.post(
        "/api/applications/does-not-exist/step1/attach-poster",
        json={"poster_id": poster["id"]},
        headers=headers,
    )
    assert response.status_code == 404
