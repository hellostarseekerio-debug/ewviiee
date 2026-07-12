"""Covers app/api/routes/posters.py end-to-end: import (parsing +
duplicate detection), CRUD, search, filters, pagination, sorting, bulk
delete, CSV export, RBAC, and validation errors."""
from __future__ import annotations

SAMPLE_TEXT = """\
沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨
https://www.dropbox.com/scl/fo/abc123/example1

【20260701-滬港兩地「跨境通辦」正式開通！】
https://www.dropbox.com/scl/fo/def456/example2
"""


def test_import_parses_and_creates_records(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["total_parsed"] == 2
    assert body["imported"] == 2
    assert body["duplicates"] == 0
    assert body["invalid"] == 0
    assert all(r["status"] == "imported" and r["id"] for r in body["results"])


def test_reimporting_the_same_text_reports_duplicates_not_errors(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 0
    assert body["duplicates"] == 2


def test_import_pasting_the_same_link_twice_in_one_batch_only_creates_one(bootstrap_admin):
    client, headers = bootstrap_admin
    text = (
        "Record A\nhttps://www.dropbox.com/scl/fo/same-link\n\n"
        "Record B (same link again)\nhttps://www.dropbox.com/scl/fo/same-link\n"
    )
    response = client.post("/api/posters/import", json={"text": text}, headers=headers)
    body = response.json()
    assert body["imported"] == 1
    assert body["duplicates"] == 1


def test_import_requires_editor_role(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "viewer1", "password": "SuperSecret123!", "role": "viewer"},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": "viewer1", "password": "SuperSecret123!"})
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=viewer_headers)
    assert response.status_code == 403


def test_list_posters_after_import(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.get("/api/posters", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["results"]) == 2


def test_list_posters_filters_by_district(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.get("/api/posters", params={"district": "Sha Tin"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["district"] == "Sha Tin"


def test_list_posters_filters_by_has_dropbox(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    client.post(
        "/api/posters",
        json={"poster_title": "No link yet", "dropbox_url": None},
        headers=headers,
    )

    with_link = client.get("/api/posters", params={"has_dropbox": "true"}, headers=headers)
    assert with_link.json()["total"] == 2

    without_link = client.get("/api/posters", params={"has_dropbox": "false"}, headers=headers)
    assert without_link.json()["total"] == 1
    assert without_link.json()["results"][0]["dropbox_url"] is None


def test_list_posters_pagination_and_sorting(bootstrap_admin):
    client, headers = bootstrap_admin
    for i in range(5):
        client.post(
            "/api/posters",
            json={"poster_title": f"Poster {i}", "dropbox_url": f"https://www.dropbox.com/scl/fo/page-{i}"},
            headers=headers,
        )
    page1 = client.get("/api/posters", params={"skip": 0, "limit": 2, "sort_by": "poster_title", "sort_dir": "asc"}, headers=headers)
    assert page1.status_code == 200
    assert page1.json()["total"] == 5
    assert len(page1.json()["results"]) == 2
    assert page1.json()["results"][0]["poster_title"] == "Poster 0"


def test_search_posters_by_keyword(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.get("/api/posters/search", params={"q": "跨境通辦"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert "跨境通辦" in body["results"][0]["poster_title"]


def test_search_posters_by_dropbox_url(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.get("/api/posters/search", params={"q": "abc123"}, headers=headers)
    assert response.json()["total"] == 1


def test_get_update_and_delete_single_poster(bootstrap_admin):
    client, headers = bootstrap_admin
    create = client.post(
        "/api/posters",
        json={"poster_title": "Draft", "dropbox_url": "https://www.dropbox.com/scl/fo/draft"},
        headers=headers,
    )
    assert create.status_code == 201
    poster_id = create.json()["id"]

    fetched = client.get(f"/api/posters/{poster_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["poster_title"] == "Draft"

    updated = client.patch(f"/api/posters/{poster_id}", json={"poster_title": "Final", "notes": "reviewed"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["poster_title"] == "Final"
    assert updated.json()["notes"] == "reviewed"

    deleted = client.delete(f"/api/posters/{poster_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/posters/{poster_id}", headers=headers).status_code == 404


def test_delete_requires_admin_not_just_editor(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    client.post(
        "/api/auth/admin/users",
        json={"username": "editor1", "password": "SuperSecret123!", "role": "editor"},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": "editor1", "password": "SuperSecret123!"})
    editor_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = client.post(
        "/api/posters",
        json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/rbac-test"},
        headers=admin_headers,
    )
    poster_id = create.json()["id"]

    response = client.delete(f"/api/posters/{poster_id}", headers=editor_headers)
    assert response.status_code == 403


def test_create_rejects_invalid_dropbox_url(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post(
        "/api/posters",
        json={"poster_title": "Bad link", "dropbox_url": "https://evil.example.com/not-dropbox"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_rejects_duplicate_dropbox_url(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post(
        "/api/posters",
        json={"poster_title": "First", "dropbox_url": "https://www.dropbox.com/scl/fo/dup"},
        headers=headers,
    )
    response = client.post(
        "/api/posters",
        json={"poster_title": "Second", "dropbox_url": "https://www.dropbox.com/scl/fo/dup"},
        headers=headers,
    )
    assert response.status_code == 409


def test_update_rejects_invalid_dropbox_url(bootstrap_admin):
    client, headers = bootstrap_admin
    create = client.post(
        "/api/posters",
        json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/update-test"},
        headers=headers,
    )
    poster_id = create.json()["id"]
    response = client.patch(f"/api/posters/{poster_id}", json={"dropbox_url": "not-a-url"}, headers=headers)
    assert response.status_code == 422


def test_workflow_steps_are_stored_as_structured_data(bootstrap_admin):
    client, headers = bootstrap_admin
    steps = [
        {"step": 1, "action": "Generate application PDF"},
        {"step": 2, "action": "Replace images"},
        {"step": 3, "action": "Export final PDF"},
    ]
    create = client.post(
        "/api/posters",
        json={
            "poster_title": "Workflow test",
            "dropbox_url": "https://www.dropbox.com/scl/fo/workflow-test",
            "workflow_steps": steps,
        },
        headers=headers,
    )
    assert create.status_code == 201
    stored = create.json()["workflow_steps"]
    assert [{"step": s["step"], "action": s["action"]} for s in stored] == steps


def test_bulk_delete_requires_admin(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    ids = []
    for i in range(3):
        create = client.post(
            "/api/posters",
            json={"poster_title": f"Bulk {i}", "dropbox_url": f"https://www.dropbox.com/scl/fo/bulk-{i}"},
            headers=admin_headers,
        )
        ids.append(create.json()["id"])

    response = client.post("/api/posters/bulk-delete", json={"ids": ids}, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["deleted"] == 3
    assert client.get("/api/posters", headers=admin_headers).json()["total"] == 0


def test_csv_export_contains_imported_records(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post("/api/posters/import", json={"text": SAMPLE_TEXT}, headers=headers)
    response = client.get("/api/posters/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    csv_text = response.text
    assert "dropbox_url" in csv_text.splitlines()[0]
    assert "Sha Tin" in csv_text


def test_malformed_import_text_returns_zero_records_not_an_error(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/import", json={"text": "no links here at all, just noise"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["total_parsed"] == 0
    assert response.json()["imported"] == 0


def test_import_requires_non_empty_text(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/import", json={"text": ""}, headers=headers)
    assert response.status_code == 422


def test_unauthenticated_requests_are_rejected(api_client):
    assert api_client.get("/api/posters").status_code == 401
    assert api_client.post("/api/posters/import", json={"text": SAMPLE_TEXT}).status_code == 401
