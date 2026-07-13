"""Covers app/api/routes/folders.py end-to-end: CRUD, move, delete
policies, RBAC, breadcrumbs/stats, and the whole-tree endpoint - plus how
Poster Archive wires into it (auto-suggestion on import/create, folder
filters on list/search, bulk-move)."""
from __future__ import annotations


def _make_user(client, admin_headers: dict, username: str, role: str) -> dict:
    client.post(
        "/api/auth/admin/users",
        json={"username": username, "password": "SuperSecret123!", "role": role},
        headers=admin_headers,
    )
    login = client.post("/api/auth/token", data={"username": username, "password": "SuperSecret123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_folder(client, headers, name, parent_id=None):
    response = client.post("/api/folders", json={"name": name, "parent_id": parent_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------


def test_create_and_get_folder(bootstrap_admin):
    client, headers = bootstrap_admin
    folder = _create_folder(client, headers, "Poster Archive")
    assert folder["parent_id"] is None
    assert folder["depth"] == 0
    assert folder["path"] == folder["id"]

    detail = client.get(f"/api/folders/{folder['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["folder"]["name"] == "Poster Archive"
    assert body["breadcrumbs"] == [body["folder"]]
    assert body["stats"]["total_items"] == 0


def test_nested_folder_breadcrumbs(bootstrap_admin):
    client, headers = bootstrap_admin
    root = _create_folder(client, headers, "Root")
    year = _create_folder(client, headers, "2026", parent_id=root["id"])
    month = _create_folder(client, headers, "07 - July", parent_id=year["id"])

    detail = client.get(f"/api/folders/{month['id']}", headers=headers).json()
    names = [f["name"] for f in detail["breadcrumbs"]]
    assert names == ["Root", "2026", "07 - July"]


def test_create_folder_requires_editor(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    viewer_headers = _make_user(client, admin_headers, "viewer_f", "viewer")
    response = client.post("/api/folders", json={"name": "X"}, headers=viewer_headers)
    assert response.status_code == 403


def test_create_folder_under_unknown_parent_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post("/api/folders", json={"name": "X", "parent_id": "nope"}, headers=headers)
    assert response.status_code == 404


def test_duplicate_sibling_name_is_409(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_folder(client, headers, "Sha Tin")
    response = client.post("/api/folders", json={"name": "Sha Tin"}, headers=headers)
    assert response.status_code == 409


def test_rename_folder(bootstrap_admin):
    client, headers = bootstrap_admin
    folder = _create_folder(client, headers, "Old")
    response = client.patch(f"/api/folders/{folder['id']}", json={"name": "New"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_rename_requires_editor(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    folder = _create_folder(client, admin_headers, "Folder")
    viewer_headers = _make_user(client, admin_headers, "viewer_rename", "viewer")
    response = client.patch(f"/api/folders/{folder['id']}", json={"name": "New"}, headers=viewer_headers)
    assert response.status_code == 403


def test_move_folder_updates_parent(bootstrap_admin):
    client, headers = bootstrap_admin
    a = _create_folder(client, headers, "A")
    b = _create_folder(client, headers, "B")
    child = _create_folder(client, headers, "Child", parent_id=a["id"])

    response = client.post(f"/api/folders/{child['id']}/move", json={"parent_id": b["id"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["parent_id"] == b["id"]


def test_move_folder_into_own_subtree_is_409(bootstrap_admin):
    client, headers = bootstrap_admin
    root = _create_folder(client, headers, "Root")
    child = _create_folder(client, headers, "Child", parent_id=root["id"])
    response = client.post(f"/api/folders/{root['id']}/move", json={"parent_id": child["id"]}, headers=headers)
    assert response.status_code == 409


def test_delete_empty_folder_requires_admin(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    editor_headers = _make_user(client, admin_headers, "editor_del", "editor")
    folder = _create_folder(client, admin_headers, "ToDelete")
    response = client.delete(f"/api/folders/{folder['id']}", headers=editor_headers)
    assert response.status_code == 403
    response = client.delete(f"/api/folders/{folder['id']}", headers=admin_headers)
    assert response.status_code == 204


def test_delete_non_empty_folder_requires_recursive(bootstrap_admin):
    client, headers = bootstrap_admin
    root = _create_folder(client, headers, "Root")
    _create_folder(client, headers, "Child", parent_id=root["id"])
    response = client.delete(f"/api/folders/{root['id']}", headers=headers)
    assert response.status_code == 409
    response = client.delete(f"/api/folders/{root['id']}?recursive=true", headers=headers)
    assert response.status_code == 204


def test_delete_unknown_folder_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.delete("/api/folders/nope", headers=headers)
    assert response.status_code == 404


def test_list_children_of_root(bootstrap_admin):
    client, headers = bootstrap_admin
    _create_folder(client, headers, "A")
    _create_folder(client, headers, "B")
    response = client.get("/api/folders", headers=headers)
    assert response.status_code == 200
    names = {f["name"] for f in response.json()}
    assert {"A", "B"}.issubset(names)


def test_folder_tree_endpoint_reflects_poster_counts(bootstrap_admin):
    client, headers = bootstrap_admin
    folder = _create_folder(client, headers, "HasPosters")
    client.post(
        "/api/posters",
        json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/tree-test", "folder_id": folder["id"]},
        headers=headers,
    )
    tree = client.get("/api/folders/tree?resource_type=poster", headers=headers)
    assert tree.status_code == 200
    node = next(n for n in tree.json() if n["id"] == folder["id"])
    assert node["direct_items"] == 1
    assert node["total_items"] == 1


def test_unauthenticated_folder_requests_are_rejected(api_client):
    assert api_client.get("/api/folders").status_code == 401
    assert api_client.post("/api/folders", json={"name": "X"}).status_code == 401


# ---------------------------------------------------------------------------
# Poster <-> Folder integration
# ---------------------------------------------------------------------------


def test_creating_poster_without_folder_id_auto_files_it(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.post(
        "/api/posters",
        json={
            "poster_title": "Auto-filed",
            "district": "Sha Tin",
            "estate": "Yue Chui Court",
            "poster_type": "notice",
            "document_date": "2026-07-07T00:00:00",
            "dropbox_url": "https://www.dropbox.com/scl/fo/autofile-test",
        },
        headers=headers,
    )
    assert response.status_code == 201
    poster = response.json()
    assert poster["folder_id"] is not None

    detail = client.get(f"/api/folders/{poster['folder_id']}", headers=headers).json()
    assert detail["folder"]["name"] == "Notice"
    names = [f["name"] for f in detail["breadcrumbs"]]
    assert names == ["Poster Archive", "2026", "07 - July", "Sha Tin", "Yue Chui Court", "Notice"]


def test_creating_poster_with_explicit_folder_id_overrides_suggestion(bootstrap_admin):
    client, headers = bootstrap_admin
    manual_folder = _create_folder(client, headers, "My Manual Folder")
    response = client.post(
        "/api/posters",
        json={
            "poster_title": "Manually filed",
            "district": "Sha Tin",
            "dropbox_url": "https://www.dropbox.com/scl/fo/manual-file-test",
            "folder_id": manual_folder["id"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["folder_id"] == manual_folder["id"]


def test_repeat_imports_reuse_the_same_auto_created_folders(bootstrap_admin):
    client, headers = bootstrap_admin
    # Both lines use "通告" (notice) so they share district/estate/type/
    # month and land in the same auto-created folder chain.
    text = (
        "沙田 20260707-通告-73H-愉翠苑來往大埔富蝶邨\n"
        "https://www.dropbox.com/scl/fo/reuse-folder-1\n"
        "沙田 20260708-通告-73H-愉翠苑\n"
        "https://www.dropbox.com/scl/fo/reuse-folder-2\n"
    )
    response = client.post("/api/posters/import", json={"text": text}, headers=headers)
    assert response.status_code == 201
    ids = [r["id"] for r in response.json()["results"] if r["id"]]
    folder_ids = set()
    for poster_id in ids:
        poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
        folder_ids.add(poster["folder_id"])
    assert len(folder_ids) == 1  # both records share district/estate/month -> one folder


def test_import_with_folder_id_override_files_whole_batch_there(bootstrap_admin):
    client, headers = bootstrap_admin
    target = _create_folder(client, headers, "Batch Target")
    text = (
        "沙田 20260707-海報-好消息\nhttps://www.dropbox.com/scl/fo/batch-override-1\n"
        "觀塘 20260710-通告\nhttps://www.dropbox.com/scl/fo/batch-override-2\n"
    )
    response = client.post("/api/posters/import", json={"text": text, "folder_id": target["id"]}, headers=headers)
    assert response.status_code == 201
    ids = [r["id"] for r in response.json()["results"] if r["id"]]
    for poster_id in ids:
        poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
        assert poster["folder_id"] == target["id"]


def test_updating_poster_folder_id_moves_it(bootstrap_admin):
    client, headers = bootstrap_admin
    create = client.post(
        "/api/posters", json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/move-test"},
        headers=headers,
    )
    poster_id = create.json()["id"]
    target = _create_folder(client, headers, "Destination")
    response = client.patch(f"/api/posters/{poster_id}", json={"folder_id": target["id"]}, headers=headers)
    assert response.status_code == 200
    assert response.json()["folder_id"] == target["id"]


def test_updating_poster_with_unknown_folder_id_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    create = client.post(
        "/api/posters", json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/bad-folder-test"},
        headers=headers,
    )
    poster_id = create.json()["id"]
    response = client.patch(f"/api/posters/{poster_id}", json={"folder_id": "nope"}, headers=headers)
    assert response.status_code == 404


def test_listing_posters_by_folder_id_recursive(bootstrap_admin):
    client, headers = bootstrap_admin
    root = _create_folder(client, headers, "Root")
    child = _create_folder(client, headers, "Child", parent_id=root["id"])
    client.post(
        "/api/posters",
        json={"poster_title": "In root", "dropbox_url": "https://www.dropbox.com/scl/fo/folder-list-1", "folder_id": root["id"]},
        headers=headers,
    )
    client.post(
        "/api/posters",
        json={"poster_title": "In child", "dropbox_url": "https://www.dropbox.com/scl/fo/folder-list-2", "folder_id": child["id"]},
        headers=headers,
    )

    recursive = client.get(f"/api/posters?folder_id={root['id']}&recursive=true", headers=headers)
    assert recursive.json()["total"] == 2

    non_recursive = client.get(f"/api/posters?folder_id={root['id']}&recursive=false", headers=headers)
    assert non_recursive.json()["total"] == 1


def test_listing_posters_by_unknown_folder_id_is_404(bootstrap_admin):
    client, headers = bootstrap_admin
    response = client.get("/api/posters?folder_id=nope", headers=headers)
    assert response.status_code == 404


def test_bulk_move_posters(bootstrap_admin):
    client, headers = bootstrap_admin
    p1 = client.post(
        "/api/posters", json={"poster_title": "A", "dropbox_url": "https://www.dropbox.com/scl/fo/bulkmove-1"},
        headers=headers,
    ).json()
    p2 = client.post(
        "/api/posters", json={"poster_title": "B", "dropbox_url": "https://www.dropbox.com/scl/fo/bulkmove-2"},
        headers=headers,
    ).json()
    target = _create_folder(client, headers, "Bulk Target")

    response = client.post(
        "/api/posters/bulk-move", json={"ids": [p1["id"], p2["id"]], "folder_id": target["id"]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["moved"] == 2

    for poster_id in (p1["id"], p2["id"]):
        poster = client.get(f"/api/posters/{poster_id}", headers=headers).json()
        assert poster["folder_id"] == target["id"]


def test_bulk_move_requires_editor(bootstrap_admin):
    client, admin_headers = bootstrap_admin
    viewer_headers = _make_user(client, admin_headers, "viewer_bulkmove", "viewer")
    response = client.post("/api/posters/bulk-move", json={"ids": ["x"], "folder_id": None}, headers=viewer_headers)
    assert response.status_code == 403


def test_deleting_folder_recursively_unfiles_posters_not_deletes_them(bootstrap_admin):
    client, headers = bootstrap_admin
    folder = _create_folder(client, headers, "ToDelete")
    poster = client.post(
        "/api/posters",
        json={"poster_title": "X", "dropbox_url": "https://www.dropbox.com/scl/fo/folder-delete-test", "folder_id": folder["id"]},
        headers=headers,
    ).json()

    response = client.delete(f"/api/folders/{folder['id']}?recursive=true", headers=headers)
    assert response.status_code == 204

    still_there = client.get(f"/api/posters/{poster['id']}", headers=headers)
    assert still_there.status_code == 200
    assert still_there.json()["folder_id"] is None
