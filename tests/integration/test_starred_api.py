"""Covers app/api/routes/starred.py - per-user favorites, reusable across
resource types (StarredItem, app/core/models.py)."""
from __future__ import annotations


def _make_user(client, admin_headers: dict, username: str, role: str) -> dict:
    client.post(
        "/api/auth/admin/users",
        json={"username": username, "password": "SuperSecret123!", "role": role},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": username, "password": "SuperSecret123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_star_and_list(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/starred", json={"resource_type": "poster", "resource_id": "poster-1"}, headers=headers)
    assert response.status_code == 201

    listed = client.get("/api/starred?resource_type=poster", headers=headers)
    assert listed.status_code == 200
    assert any(item["resource_id"] == "poster-1" for item in listed.json())


def test_starring_twice_is_idempotent_not_a_conflict(bootstrap_admin):
    client, headers = bootstrap_admin
    first = client.post("/api/starred", json={"resource_type": "poster", "resource_id": "dup"}, headers=headers)
    second = client.post("/api/starred", json={"resource_type": "poster", "resource_id": "dup"}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201  # no-op, not 409

    listed = client.get("/api/starred?resource_type=poster", headers=headers).json()
    assert sum(1 for item in listed if item["resource_id"] == "dup") == 1


def test_unstar_removes_it(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/starred", json={"resource_type": "poster", "resource_id": "to-remove"}, headers=headers)
    response = client.delete("/api/starred/poster/to-remove", headers=headers)
    assert response.status_code == 204

    listed = client.get("/api/starred?resource_type=poster", headers=headers).json()
    assert not any(item["resource_id"] == "to-remove" for item in listed)


def test_stars_are_per_user(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    editor_headers = _make_user(client, admin_headers, "editor_star", "editor")

    client.post("/api/starred", json={"resource_type": "poster", "resource_id": "admin-only"}, headers=admin_headers)

    admin_list = client.get("/api/starred?resource_type=poster", headers=admin_headers).json()
    editor_list = client.get("/api/starred?resource_type=poster", headers=editor_headers).json()
    assert any(item["resource_id"] == "admin-only" for item in admin_list)
    assert not any(item["resource_id"] == "admin-only" for item in editor_list)


def test_unauthenticated_starred_requests_are_rejected(api_client):
    assert api_client.get("/api/starred").status_code == 401
    assert api_client.post("/api/starred", json={"resource_type": "poster", "resource_id": "x"}).status_code == 401
