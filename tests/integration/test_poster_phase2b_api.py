"""Covers the Phase 2B poster endpoints: bulk field-change, bulk status,
duplicate detection, Dropbox link verification, and link-change history."""
from __future__ import annotations

import httpx


def _make_user(client, admin_headers: dict, username: str, role: str) -> dict:
    client.post(
        "/api/auth/admin/users",
        json={"username": username, "password": "SuperSecret123!", "role": role},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": username, "password": "SuperSecret123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_poster(client, headers, dropbox_url, **extra):
    payload = {"poster_title": "Test", "dropbox_url": dropbox_url, **extra}
    response = client.post("/api/posters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Bulk field-change (district/estate/poster_type/retag)
# ---------------------------------------------------------------------------


def test_bulk_update_changes_district_and_poster_type(bootstrap_admin):
    client, headers = bootstrap_admin
    p1 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-update-1")
    p2 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-update-2")

    response = client.post(
        "/api/posters/bulk-update",
        json={"ids": [p1["id"], p2["id"]], "district": "Sha Tin", "poster_type": "notice"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    for poster_id in (p1["id"], p2["id"]):
        poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
        assert poster["district"] == "Sha Tin"
        assert poster["poster_type"] == "notice"


def test_bulk_update_add_keywords_merges_without_duplicating(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-retag", keywords=["existing"])

    response = client.post(
        "/api/posters/bulk-update",
        json={"ids": [poster["id"]], "add_keywords": ["existing", "new-tag"]},
        headers=headers,
    )
    assert response.status_code == 200

    updated = client.get(f"/api/posters/{poster['id']}", headers=headers).json()
    assert sorted(updated["keywords"]) == ["existing", "new-tag"]


def test_bulk_update_requires_editor(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    viewer_headers = _make_user(client, admin_headers, "viewer_bulkupdate", "viewer")
    response = client.post(
        "/api/posters/bulk-update", json={"ids": ["x"], "district": "Sha Tin"}, headers=viewer_headers
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Bulk status change
# ---------------------------------------------------------------------------


def test_bulk_status_change_applies_to_all_valid_records(bootstrap_admin):
    client, headers = bootstrap_admin
    p1 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-status-1")
    p2 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-status-2")

    response = client.post(
        "/api/posters/bulk-status", json={"ids": [p1["id"], p2["id"]], "status": "approved"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] == 2
    assert body["skipped"] == []

    for poster_id in (p1["id"], p2["id"]):
        poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
        assert poster["status"] == "approved"


def test_bulk_status_change_skips_invalid_transitions_without_failing_others(bootstrap_admin):
    client, headers = bootstrap_admin
    p1 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-status-skip-1")  # pending_review
    p2 = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-status-skip-2")
    client.post(f"/api/posters/{p2['id']}/status", json={"status": "archived", "force": True}, headers=headers)

    # pending_review -> published is invalid; archived -> published is also invalid.
    response = client.post(
        "/api/posters/bulk-status", json={"ids": [p1["id"], p2["id"]], "status": "published"}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] == 0
    assert set(body["skipped"]) == {p1["id"], p2["id"]}


def test_bulk_status_requires_reviewer_for_approve(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    viewer_headers = _make_user(client, admin_headers, "viewer_bulkstatus", "viewer")
    poster = _create_poster(client, admin_headers, "https://www.dropbox.com/scl/fo/bulk-status-rbac")
    response = client.post(
        "/api/posters/bulk-status", json={"ids": [poster["id"]], "status": "approved"}, headers=viewer_headers
    )
    assert response.status_code == 403


def test_bulk_status_unknown_status_is_422(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/bulk-status-422")
    response = client.post(
        "/api/posters/bulk-status", json={"ids": [poster["id"]], "status": "not_real"}, headers=headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_duplicates_endpoint_finds_similar_titles(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_poster(client, headers, "https://www.dropbox.com/scl/fo/dup-a", poster_title="Sha Tin notice 2026")
    _create_poster(client, headers, "https://www.dropbox.com/scl/fo/dup-b", poster_title="Sha Tin notice 2026")

    response = client.get("/api/posters/duplicates", headers=headers)
    assert response.status_code == 200
    groups = response.json()
    assert any(g["reason"] == "similar_title" for g in groups)


def test_duplicates_endpoint_empty_when_nothing_matches(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_poster(client, headers, "https://www.dropbox.com/scl/fo/unique-a", poster_title="Totally unique title one")
    response = client.get("/api/posters/duplicates", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_duplicates_requires_authentication(api_client):
    assert api_client.get("/api/posters/duplicates").status_code == 401


# ---------------------------------------------------------------------------
# Dropbox link verification
# ---------------------------------------------------------------------------


def _mock_dropbox_response(monkeypatch, status_code: int):
    class FakeResponse:
        def __init__(self):
            self.status_code = status_code

    class FakeStreamContext:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *a):
            return False

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return FakeStreamContext()

    monkeypatch.setattr(httpx, "Client", FakeClient)


def test_verify_link_marks_working_link_not_broken(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_response(monkeypatch, 200)
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/verify-ok")

    response = client.post(f"/api/posters/{poster['id']}/verify-link", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["dropbox_link_broken"] is False
    assert body["dropbox_last_verified_at"] is not None


def test_verify_link_marks_broken_link(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_response(monkeypatch, 404)
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/verify-broken")

    response = client.post(f"/api/posters/{poster['id']}/verify-link", headers=headers)
    assert response.status_code == 200
    assert response.json()["dropbox_link_broken"] is True


def test_verify_link_without_dropbox_url_is_400(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = client.post("/api/posters", json={"poster_title": "No link"}, headers=headers).json()
    response = client.post(f"/api/posters/{poster['id']}/verify-link", headers=headers)
    assert response.status_code == 400


def test_verify_link_unknown_poster_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/nope/verify-link", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Link-change history
# ---------------------------------------------------------------------------


def test_changing_dropbox_url_records_history(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/history-old")

    response = client.patch(
        f"/api/posters/{poster['id']}",
        json={"dropbox_url": "https://www.dropbox.com/scl/fo/history-new"},
        headers=headers,
    )
    assert response.status_code == 200

    history = client.get(f"/api/posters/{poster['id']}/link-history", headers=headers)
    assert history.status_code == 200
    entries = history.json()
    assert len(entries) == 1
    assert entries[0]["old_url"] == "https://www.dropbox.com/scl/fo/history-old"
    assert entries[0]["new_url"] == "https://www.dropbox.com/scl/fo/history-new"


def test_updating_without_changing_dropbox_url_records_no_history(bootstrap_admin):
    client, headers = bootstrap_admin
    poster = _create_poster(client, headers, "https://www.dropbox.com/scl/fo/history-unchanged")

    client.patch(f"/api/posters/{poster['id']}", json={"notes": "just a note"}, headers=headers)

    history = client.get(f"/api/posters/{poster['id']}/link-history", headers=headers)
    assert history.json() == []


def test_link_history_unknown_poster_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/posters/nope/link-history", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Extended metadata fields round-trip
# ---------------------------------------------------------------------------


def test_extended_metadata_fields_round_trip(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post(
        "/api/posters",
        json={
            "poster_title": "Extended fields test",
            "dropbox_url": "https://www.dropbox.com/scl/fo/extended-fields",
            "campaign_name": "Summer Safety Campaign",
            "government_department": "運輸署",
            "version": "2",
        },
        headers=headers,
    )
    assert response.status_code == 201
    poster = response.json()
    assert poster["campaign_name"] == "Summer Safety Campaign"
    assert poster["government_department"] == "運輸署"
    assert poster["version"] == "2"
    assert poster["source"] == "manual"
    assert poster["needs_review"] is False
    assert poster["dropbox_link_broken"] is None


def test_import_sets_source_to_paste_import_and_flags_low_confidence(bootstrap_admin):
    client, headers = bootstrap_admin
    text = "@@@ !!! ###\nhttps://www.dropbox.com/scl/fo/needs-review-test\n"
    response = client.post("/api/posters/import", json={"text": text}, headers=headers)
    assert response.status_code == 201
    poster_id = response.json()["results"][0]["id"]
    poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
    assert poster["source"] == "paste_import"
    assert poster["needs_review"] is True


# ---------------------------------------------------------------------------
# Fuzzy search fallback (app/rules/fuzzy.py reused for free-text search)
# ---------------------------------------------------------------------------


def test_exact_search_match_does_not_invoke_fuzzy_fallback(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_poster(client, headers, "https://www.dropbox.com/scl/fo/exact-search", poster_title="Exact Match Title")
    response = client.get("/api/posters/search?q=Exact Match", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_fuzzy_search_finds_close_typo_when_exact_match_finds_nothing(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_poster(
        client, headers, "https://www.dropbox.com/scl/fo/fuzzy-search",
        poster_title="Sha Tin Housing Estate Notice 2026",
    )
    # Deliberate typo ("Houseing") that a plain ILIKE substring match won't find.
    response = client.get("/api/posters/search?q=Sha Tin Houseing Estate Notice 2026", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_fuzzy_search_returns_empty_for_genuinely_unrelated_query(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_poster(client, headers, "https://www.dropbox.com/scl/fo/fuzzy-unrelated", poster_title="Sha Tin Notice")
    response = client.get("/api/posters/search?q=zzzzzzzzzzzzzzzzzz", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# Learned field corrections (app/posters/corrections.py): a staff-taught
# district correction for an unlisted estate must be remembered and applied
# automatically the next time that same estate name is imported.
# ---------------------------------------------------------------------------


def test_correcting_district_is_remembered_for_future_imports(bootstrap_admin):
    client, headers = bootstrap_admin
    text = "20260710-通告-40X-未知苑\nhttps://www.dropbox.com/scl/fo/learn-1\n"

    first = client.post("/api/posters/import", json={"text": text}, headers=headers)
    poster_id = first.json()["results"][0]["id"]
    poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
    assert poster["estate"] == "未知苑"
    assert poster["district"] is None

    patched = client.patch(f"/api/posters/{poster_id}", json={"district": "大埔"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["district"] == "大埔"

    text2 = "20260711-通告-41X-未知苑\nhttps://www.dropbox.com/scl/fo/learn-2\n"
    second = client.post("/api/posters/import", json={"text": text2}, headers=headers)
    poster2_id = second.json()["results"][0]["id"]
    poster2 = client.get(f"/api/posters/{poster2_id}", headers=headers).json()
    assert poster2["district"] == "大埔"
    assert poster2["extraction_sources"]["district"] == "learned"


def test_correcting_an_already_confident_district_does_not_overwrite_learning(bootstrap_admin):
    """A confidently-resolved district (from config/rules/estates.yaml)
    being edited for an unrelated reason must not silently teach the
    parser something wrong - only a low-confidence/blank district being
    filled in should be remembered."""
    client, headers = bootstrap_admin
    text = "20260710-通告-40X-愉翠苑\nhttps://www.dropbox.com/scl/fo/no-learn-1\n"
    first = client.post("/api/posters/import", json={"text": text}, headers=headers)
    poster_id = first.json()["results"][0]["id"]
    poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
    assert poster["district"] == "沙田"  # confidently resolved via config/rules/estates.yaml

    client.patch(f"/api/posters/{poster_id}", json={"district": "Some Other District"}, headers=headers)

    text2 = "20260711-通告-41X-愉翠苑\nhttps://www.dropbox.com/scl/fo/no-learn-2\n"
    second = client.post("/api/posters/import", json={"text": text2}, headers=headers)
    poster2 = client.get(f"/api/posters/{second.json()['results'][0]['id']}", headers=headers).json()
    assert poster2["district"] == "沙田"  # unaffected by the unrelated edit
