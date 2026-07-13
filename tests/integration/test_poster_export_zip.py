"""Covers POST /api/posters/export/zip and GET /api/export-jobs/{id} -
the ZIP export feature's four selection modes (selected ids, folder,
search filters, entire archive), the sync/background split, and the
Dropbox-link download path (mocked - no real network calls in tests)."""
from __future__ import annotations

import io
import zipfile

import httpx

from app.core.config import get_settings


def _create_poster(client, headers, title, dropbox_url, **extra):
    payload = {"poster_title": title, "dropbox_url": dropbox_url, **extra}
    response = client.post("/api/posters", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _mock_dropbox_ok(monkeypatch, content: bytes = b"%PDF-1.4 fake"):
    class FakeResponse:
        status_code = 200
        headers = {"content-disposition": 'attachment; filename="poster.pdf"'}

        def iter_bytes(self):
            yield content

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


def test_export_zip_by_selected_ids(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    poster = _create_poster(client, headers, "A", "https://www.dropbox.com/scl/fo/export-ids-1")

    response = client.post("/api/posters/export/zip", json={"ids": [poster["id"]]}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        assert "metadata.csv" in zf.namelist()
        assert "README.txt" in zf.namelist()


def test_export_zip_entire_archive_with_no_filters(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    _create_poster(client, headers, "A", "https://www.dropbox.com/scl/fo/export-all-1")
    _create_poster(client, headers, "B", "https://www.dropbox.com/scl/fo/export-all-2")

    response = client.post("/api/posters/export/zip", json={}, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_text = zf.read("metadata.csv").decode()
    assert csv_text.count("\n") >= 2  # header + at least 2 data rows


def test_export_zip_by_folder_recursive(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    root = client.post("/api/folders", json={"name": "ExportRoot"}, headers=headers).json()
    child = client.post("/api/folders", json={"name": "Child", "parent_id": root["id"]}, headers=headers).json()
    _create_poster(client, headers, "InRoot", "https://www.dropbox.com/scl/fo/export-folder-1", folder_id=root["id"])
    _create_poster(client, headers, "InChild", "https://www.dropbox.com/scl/fo/export-folder-2", folder_id=child["id"])

    response = client.post("/api/posters/export/zip", json={"folder_id": root["id"], "recursive": True}, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_text = zf.read("metadata.csv").decode()
    assert "InRoot" in csv_text
    assert "InChild" in csv_text


def test_export_zip_by_search_filter(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    _create_poster(client, headers, "Match", "https://www.dropbox.com/scl/fo/export-search-1", district="Sha Tin")
    _create_poster(client, headers, "NoMatch", "https://www.dropbox.com/scl/fo/export-search-2", district="Kwun Tong")

    response = client.post("/api/posters/export/zip", json={"district": "Sha Tin"}, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        csv_text = zf.read("metadata.csv").decode()
    assert "Match" in csv_text
    assert "NoMatch" not in csv_text


def test_export_zip_skips_poster_with_no_dropbox_link(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    poster = client.post("/api/posters", json={"poster_title": "NoLink"}, headers=headers).json()

    response = client.post("/api/posters/export/zip", json={"ids": [poster["id"]]}, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        readme = zf.read("README.txt").decode()
    assert "Files included: 0" in readme
    assert "Records skipped: 1" in readme


def test_export_zip_empty_selection_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/export/zip", json={"ids": ["nope"]}, headers=headers)
    assert response.status_code == 404


def test_export_zip_unknown_folder_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/posters/export/zip", json={"folder_id": "nope"}, headers=headers)
    assert response.status_code == 404


def test_export_zip_over_max_files_is_rejected(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    monkeypatch.setenv("OAP_ZIP_EXPORT_MAX_FILES", "1")
    get_settings.cache_clear()
    p1 = _create_poster(client, headers, "A", "https://www.dropbox.com/scl/fo/maxfiles-1")
    p2 = _create_poster(client, headers, "B", "https://www.dropbox.com/scl/fo/maxfiles-2")

    response = client.post("/api/posters/export/zip", json={"ids": [p1["id"], p2["id"]]}, headers=headers)
    assert response.status_code == 400
    get_settings.cache_clear()


def test_large_export_is_queued_as_a_background_job(bootstrap_admin, monkeypatch):
    client, headers = bootstrap_admin
    _mock_dropbox_ok(monkeypatch)
    monkeypatch.setenv("OAP_ZIP_EXPORT_SYNC_THRESHOLD", "1")
    get_settings.cache_clear()
    try:
        p1 = _create_poster(client, headers, "A", "https://www.dropbox.com/scl/fo/queue-1")
        p2 = _create_poster(client, headers, "B", "https://www.dropbox.com/scl/fo/queue-2")

        response = client.post("/api/posters/export/zip", json={"ids": [p1["id"], p2["id"]]}, headers=headers)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert body["total_items"] == 2

        job = client.get(f"/api/export-jobs/{body['job_id']}", headers=headers)
        assert job.status_code == 200
        # TestClient runs BackgroundTasks synchronously before the response
        # is considered complete, so by the time we poll, it has finished.
        assert job.json()["status"] == "completed"

        download = client.get(f"/api/export-jobs/{body['job_id']}/download", headers=headers)
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
    finally:
        get_settings.cache_clear()


def test_export_job_not_found_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    assert client.get("/api/export-jobs/nope", headers=headers).status_code == 404
    assert client.get("/api/export-jobs/nope/download", headers=headers).status_code == 404


def test_unauthenticated_export_is_rejected(api_client):
    assert api_client.post("/api/posters/export/zip", json={}).status_code == 401
