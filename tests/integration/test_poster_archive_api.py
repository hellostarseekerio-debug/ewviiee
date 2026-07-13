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
    response = client.get("/api/posters", params={"district": "沙田"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["district"] == "沙田"


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
    assert "沙田" in csv_text


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


# ---------------------------------------------------------------------------
# Status workflow (POST /api/posters/{id}/status) - see app/posters/status.py
# for the transition graph and role rules this exercises.
# ---------------------------------------------------------------------------


def _login(client, username: str, password: str = "SuperSecret123!") -> dict:
    response = client.post("/api/auth/token", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_user(client, admin_headers: dict, username: str, role: str) -> dict:
    client.post(
        "/api/auth/admin/users",
        json={"username": username, "password": "SuperSecret123!", "role": role},
        headers=admin_headers,
    )
    return _login(client, username)


def _create_poster(client, headers: dict, dropbox_url: str = "https://www.dropbox.com/scl/fo/status-test") -> str:
    response = client.post(
        "/api/posters", json={"poster_title": "Status test", "dropbox_url": dropbox_url}, headers=headers
    )
    return response.json()["id"]


def test_new_poster_defaults_to_pending_review(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)
    poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
    assert poster["status"] == "pending_review"
    assert poster["approval_status"] == "pending"


def test_valid_transition_updates_status_and_syncs_approval_status(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)

    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "approved"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approval_status"] == "approved"

    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "published"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "published"

    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "archived"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "archived"
    assert body["approval_status"] == "approved"


def test_rejecting_syncs_legacy_approval_status(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)
    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "rejected"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["approval_status"] == "rejected"


def test_invalid_transition_is_rejected_with_409(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)
    # pending_review -> published skips the approve/publish steps entirely.
    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "published"}, headers=headers)
    assert response.status_code == 409
    assert "pending_review" in response.json()["detail"]


def test_unknown_status_value_is_rejected_with_422(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)
    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "not_a_real_status"}, headers=headers)
    assert response.status_code == 422


def test_status_change_on_unknown_poster_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/does-not-exist/status", json={"status": "approved"}, headers=headers)
    assert response.status_code == 404


def test_setting_the_same_status_again_is_a_noop_not_an_error(bootstrap_admin):
    client, headers = bootstrap_admin
    poster_id = _create_poster(client, headers)
    response = client.post(
        f"/api/posters/{poster_id}/status", json={"status": "pending_review"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def test_viewer_cannot_change_status_at_all(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    poster_id = _create_poster(client, admin_headers)
    viewer_headers = _make_user(client, admin_headers, "viewer_status", "viewer")
    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "approved"}, headers=viewer_headers)
    assert response.status_code == 403


def test_reviewer_can_approve_and_reject(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    reviewer_headers = _make_user(client, admin_headers, "reviewer_status", "reviewer")

    poster_id = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/reviewer-approve")
    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "approved"}, headers=reviewer_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    poster_id_2 = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/reviewer-reject")
    response = client.post(f"/api/posters/{poster_id_2}/status", json={"status": "rejected"}, headers=reviewer_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_reviewer_cannot_perform_editor_only_transitions(bootstrap_admin):
    """Approve is Reviewer+, but publishing an already-approved poster is an
    Editor+ operational step - a plain Reviewer account must not be able
    to do it."""
    client, admin_headers = bootstrap_admin
    reviewer_headers = _make_user(client, admin_headers, "reviewer_status2", "reviewer")

    poster_id = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/reviewer-publish-blocked")
    approve = client.post(f"/api/posters/{poster_id}/status", json={"status": "approved"}, headers=admin_headers)
    assert approve.status_code == 200

    response = client.post(f"/api/posters/{poster_id}/status", json={"status": "published"}, headers=reviewer_headers)
    assert response.status_code == 403


def test_editor_can_perform_both_review_and_editor_transitions(bootstrap_admin):
    """_ROLE_RANK ranks Editor above Reviewer, so an Editor account must be
    able to do everything a Reviewer can plus the Editor-only steps."""
    client, admin_headers = bootstrap_admin
    editor_headers = _make_user(client, admin_headers, "editor_status", "editor")

    poster_id = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/editor-full-flow")
    approve = client.post(f"/api/posters/{poster_id}/status", json={"status": "approved"}, headers=editor_headers)
    assert approve.status_code == 200
    publish = client.post(f"/api/posters/{poster_id}/status", json={"status": "published"}, headers=editor_headers)
    assert publish.status_code == 200
    archive = client.post(f"/api/posters/{poster_id}/status", json={"status": "archived"}, headers=editor_headers)
    assert archive.status_code == 200


def test_admin_force_bypasses_the_transition_graph(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    poster_id = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/force-test")
    # pending_review -> archived is not a normally-allowed transition.
    response = client.post(
        f"/api/posters/{poster_id}/status",
        json={"status": "archived", "force": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_non_admin_force_flag_is_ignored(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    editor_headers = _make_user(client, admin_headers, "editor_force", "editor")
    poster_id = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/editor-force-test")
    response = client.post(
        f"/api/posters/{poster_id}/status",
        json={"status": "archived", "force": True},
        headers=editor_headers,
    )
    assert response.status_code == 409


def test_list_posters_filters_by_status(bootstrap_admin):
    client, headers = bootstrap_admin
    p1 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/status-filter-1")
    p2 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/status-filter-2")
    client.post(f"/api/posters/{p2}/status", json={"status": "archived", "force": True}, headers=headers)

    pending = client.get("/api/posters?status=pending_review", headers=headers).json()
    archived = client.get("/api/posters?status=archived", headers=headers).json()

    assert p1 in [r["id"] for r in pending["results"]]
    assert p2 not in [r["id"] for r in pending["results"]]
    assert p2 in [r["id"] for r in archived["results"]]


def test_list_posters_unknown_status_filter_is_422(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/posters?status=not_a_status", headers=headers)
    assert response.status_code == 422
