"""Covers GET /api/dashboard/stats - including the Phase 2B additions
(poster breakdowns, broken links, duplicates, downloads today, pending
reviews, most active users, export storage)."""
from __future__ import annotations


def test_dashboard_stats_requires_authentication(api_client):
    assert api_client.get("/api/dashboard/stats").status_code == 401


def test_dashboard_stats_on_empty_system(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/dashboard/stats", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_posters"] == 0
    assert body["posters_by_district"] == {}
    assert body["broken_dropbox_links"] == 0
    assert body["duplicate_poster_groups"] == 0
    assert body["pending_reviews"] == 0
    assert body["export_storage_bytes"] == 0


def test_dashboard_reflects_poster_counts_by_district_and_status(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post(
        "/api/posters",
        json={"poster_title": "A", "district": "Sha Tin", "dropbox_url": "https://www.dropbox.com/scl/fo/dash-1"},
        headers=headers,
    )
    client.post(
        "/api/posters",
        json={"poster_title": "B", "district": "Sha Tin", "dropbox_url": "https://www.dropbox.com/scl/fo/dash-2"},
        headers=headers,
    )

    response = client.get("/api/dashboard/stats", headers=headers)
    body = response.json()
    assert body["total_posters"] == 2
    assert body["posters_by_district"]["Sha Tin"] == 2
    assert body["posters_by_status"]["pending_review"] == 2
    assert body["pending_reviews"] == 2
    assert len(body["recent_poster_uploads"]) == 2


def test_dashboard_counts_broken_links_and_records_download_activity(bootstrap_admin, monkeypatch):
    import httpx

    client, headers = bootstrap_admin
    poster = client.post(
        "/api/posters",
        json={"poster_title": "Broken", "dropbox_url": "https://www.dropbox.com/scl/fo/dash-broken"},
        headers=headers,
    ).json()

    class FakeResponse:
        status_code = 404

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
    client.post(f"/api/posters/{poster['id']}/verify-link", headers=headers)

    # CSV export counts toward "downloads today".
    client.get("/api/posters/export", headers=headers)

    response = client.get("/api/dashboard/stats", headers=headers)
    body = response.json()
    assert body["broken_dropbox_links"] == 1
    assert body["downloads_today"] >= 1


def test_dashboard_most_active_users_reflects_audit_log(bootstrap_admin):
    client, headers = bootstrap_admin
    client.post(
        "/api/posters",
        json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/dash-active"},
        headers=headers,
    )
    response = client.get("/api/dashboard/stats", headers=headers)
    body = response.json()
    assert any(u["actor"] == "admin" for u in body["most_active_users"])
