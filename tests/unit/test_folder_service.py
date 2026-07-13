"""Covers app/folders/service.py - the generic, resource-agnostic folder
engine (create/rename/move/delete, breadcrumbs, subtree lookup, stats).
Uses an in-memory SQLite database with the real ORM models, and Poster as
the "item_model" stand-in since it's the one resource wired to folders
today - the service itself never imports Poster."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.models import Base, Poster
from app.folders.service import (
    FolderError,
    FolderNotFoundError,
    create_folder,
    delete_folder,
    get_breadcrumbs,
    get_folder_or_raise,
    get_folder_stats,
    get_full_tree_with_counts,
    list_children,
    move_folder,
    rename_folder,
    subtree_folder_ids,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_create_folder_sets_path_and_depth_for_root(db):
    folder = create_folder(db, name="Poster Archive", parent_id=None, created_by="admin")
    assert folder.path == folder.id
    assert folder.depth == 0


def test_create_nested_folder_builds_path_from_ancestors(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    year = create_folder(db, name="2026", parent_id=root.id, created_by="admin")
    month = create_folder(db, name="07 - July", parent_id=year.id, created_by="admin")
    assert month.path == f"{root.id}/{year.id}/{month.id}"
    assert month.depth == 2


def test_create_folder_strips_whitespace_from_name(db):
    folder = create_folder(db, name="  Sha Tin  ", parent_id=None, created_by="admin")
    assert folder.name == "Sha Tin"


def test_create_folder_rejects_empty_name(db):
    with pytest.raises(FolderError):
        create_folder(db, name="   ", parent_id=None, created_by="admin")


def test_create_folder_rejects_duplicate_sibling_name_case_insensitive(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    create_folder(db, name="2026", parent_id=root.id, created_by="admin")
    with pytest.raises(FolderError):
        create_folder(db, name="2026", parent_id=root.id, created_by="admin")
    with pytest.raises(FolderError):
        create_folder(db, name="2026", parent_id=root.id, created_by="admin")


def test_create_folder_allows_same_name_under_different_parents(db):
    a = create_folder(db, name="A", parent_id=None, created_by="admin")
    b = create_folder(db, name="B", parent_id=None, created_by="admin")
    create_folder(db, name="Shared", parent_id=a.id, created_by="admin")
    # must not raise - "Shared" under B is a different sibling group
    create_folder(db, name="Shared", parent_id=b.id, created_by="admin")


def test_create_folder_under_unknown_parent_raises_not_found(db):
    with pytest.raises(FolderNotFoundError):
        create_folder(db, name="X", parent_id="does-not-exist", created_by="admin")


def test_get_folder_or_raise_unknown_id(db):
    with pytest.raises(FolderNotFoundError):
        get_folder_or_raise(db, "nope")


def test_rename_folder_updates_name(db):
    folder = create_folder(db, name="Old Name", parent_id=None, created_by="admin")
    renamed = rename_folder(db, folder.id, "New Name")
    assert renamed.name == "New Name"


def test_rename_folder_rejects_conflicting_sibling_name(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    create_folder(db, name="Existing", parent_id=root.id, created_by="admin")
    target = create_folder(db, name="ToRename", parent_id=root.id, created_by="admin")
    with pytest.raises(FolderError):
        rename_folder(db, target.id, "Existing")


def test_rename_folder_to_its_own_current_name_does_not_raise(db):
    folder = create_folder(db, name="Same", parent_id=None, created_by="admin")
    rename_folder(db, folder.id, "Same")  # excludes itself from the conflict check


def test_list_children_ordered_by_name(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    create_folder(db, name="Zebra", parent_id=root.id, created_by="admin")
    create_folder(db, name="Alpha", parent_id=root.id, created_by="admin")
    children = list_children(db, root.id)
    assert [c.name for c in children] == ["Alpha", "Zebra"]


def test_get_breadcrumbs_root_to_self_order(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    year = create_folder(db, name="2026", parent_id=root.id, created_by="admin")
    month = create_folder(db, name="July", parent_id=year.id, created_by="admin")
    crumbs = get_breadcrumbs(db, month)
    assert [c.name for c in crumbs] == ["Root", "2026", "July"]


def test_subtree_folder_ids_includes_all_descendants(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    a = create_folder(db, name="A", parent_id=root.id, created_by="admin")
    create_folder(db, name="B", parent_id=a.id, created_by="admin")
    other = create_folder(db, name="Unrelated", parent_id=None, created_by="admin")

    ids = subtree_folder_ids(db, root, include_self=True)
    assert len(ids) == 3
    assert other.id not in ids


def test_subtree_folder_ids_can_exclude_self(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    ids = subtree_folder_ids(db, root, include_self=False)
    assert ids == [child.id]


def test_move_folder_updates_parent_path_and_depth(db):
    root_a = create_folder(db, name="A", parent_id=None, created_by="admin")
    root_b = create_folder(db, name="B", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root_a.id, created_by="admin")

    moved = move_folder(db, child.id, root_b.id)
    assert moved.parent_id == root_b.id
    assert moved.path == f"{root_b.id}/{child.id}"
    assert moved.depth == 1


def test_move_folder_rewrites_descendant_paths_too(db):
    root_a = create_folder(db, name="A", parent_id=None, created_by="admin")
    root_b = create_folder(db, name="B", parent_id=None, created_by="admin")
    mid = create_folder(db, name="Mid", parent_id=root_a.id, created_by="admin")
    leaf = create_folder(db, name="Leaf", parent_id=mid.id, created_by="admin")

    move_folder(db, mid.id, root_b.id)
    db.refresh(leaf)
    assert leaf.path == f"{root_b.id}/{mid.id}/{leaf.id}"
    assert leaf.depth == 2
    assert [c.name for c in get_breadcrumbs(db, leaf)] == ["B", "Mid", "Leaf"]


def test_move_folder_to_root_sets_parent_none(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    moved = move_folder(db, child.id, None)
    assert moved.parent_id is None
    assert moved.path == child.id
    assert moved.depth == 0


def test_move_folder_into_itself_raises(db):
    folder = create_folder(db, name="X", parent_id=None, created_by="admin")
    with pytest.raises(FolderError):
        move_folder(db, folder.id, folder.id)


def test_move_folder_into_own_descendant_raises(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    grandchild = create_folder(db, name="Grandchild", parent_id=child.id, created_by="admin")
    with pytest.raises(FolderError):
        move_folder(db, root.id, grandchild.id)
    with pytest.raises(FolderError):
        move_folder(db, root.id, child.id)


def test_move_folder_rejects_destination_name_conflict(db):
    root_a = create_folder(db, name="A", parent_id=None, created_by="admin")
    root_b = create_folder(db, name="B", parent_id=None, created_by="admin")
    create_folder(db, name="Same", parent_id=root_b.id, created_by="admin")
    mover = create_folder(db, name="Same", parent_id=root_a.id, created_by="admin")
    with pytest.raises(FolderError):
        move_folder(db, mover.id, root_b.id)


def test_move_folder_to_same_parent_is_a_noop(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    result = move_folder(db, child.id, root.id)
    assert result.id == child.id
    assert result.parent_id == root.id


def test_delete_empty_folder_succeeds_without_recursive(db):
    folder = create_folder(db, name="Empty", parent_id=None, created_by="admin")
    delete_folder(db, folder.id, item_model=Poster, recursive=False)
    with pytest.raises(FolderNotFoundError):
        get_folder_or_raise(db, folder.id)


def test_delete_folder_with_subfolders_requires_recursive(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    with pytest.raises(FolderError):
        delete_folder(db, root.id, item_model=Poster, recursive=False)


def test_delete_folder_with_items_requires_recursive(db):
    folder = create_folder(db, name="HasItems", parent_id=None, created_by="admin")
    db.add(Poster(poster_title="X", dropbox_url="https://www.dropbox.com/x", folder_id=folder.id))
    db.commit()
    with pytest.raises(FolderError):
        delete_folder(db, folder.id, item_model=Poster, recursive=False)


def test_recursive_delete_unfiles_items_instead_of_deleting_them(db):
    folder = create_folder(db, name="HasItems", parent_id=None, created_by="admin")
    poster = Poster(poster_title="X", dropbox_url="https://www.dropbox.com/x", folder_id=folder.id)
    db.add(poster)
    db.commit()
    poster_id = poster.id

    delete_folder(db, folder.id, item_model=Poster, recursive=True)

    still_there = db.get(Poster, poster_id)
    assert still_there is not None  # never deleted, only unfiled
    assert still_there.folder_id is None


def test_recursive_delete_removes_every_descendant_folder(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    grandchild = create_folder(db, name="Grandchild", parent_id=child.id, created_by="admin")
    # Capture ids before deleting - the ORM instances themselves become
    # detached once their rows are gone (synchronize_session="fetch"),
    # matching how a real caller would only ever have kept the id string.
    ids = (root.id, child.id, grandchild.id)

    delete_folder(db, root.id, item_model=Poster, recursive=True)

    for folder_id in ids:
        with pytest.raises(FolderNotFoundError):
            get_folder_or_raise(db, folder_id)


def test_delete_unknown_folder_raises_not_found(db):
    with pytest.raises(FolderNotFoundError):
        delete_folder(db, "nope", item_model=Poster, recursive=True)


def test_folder_stats_direct_vs_total(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    db.add(Poster(poster_title="Root item", dropbox_url="https://www.dropbox.com/1", folder_id=root.id))
    db.add(Poster(poster_title="Child item", dropbox_url="https://www.dropbox.com/2", folder_id=child.id))
    db.commit()

    stats = get_folder_stats(db, root, item_model=Poster)
    assert stats.direct_subfolders == 1
    assert stats.direct_items == 1
    assert stats.total_subfolders == 1
    assert stats.total_items == 2


def test_full_tree_with_counts_rolls_up_recursively(db):
    root = create_folder(db, name="Root", parent_id=None, created_by="admin")
    child = create_folder(db, name="Child", parent_id=root.id, created_by="admin")
    db.add(Poster(poster_title="A", dropbox_url="https://www.dropbox.com/a", folder_id=root.id))
    db.add(Poster(poster_title="B", dropbox_url="https://www.dropbox.com/b", folder_id=child.id))
    db.add(Poster(poster_title="C", dropbox_url="https://www.dropbox.com/c", folder_id=child.id))
    db.commit()

    tree = get_full_tree_with_counts(db, item_model=Poster)
    assert len(tree) == 1
    root_node = tree[0]
    assert root_node.direct_items == 1
    assert root_node.total_items == 3  # 1 direct + 2 from child
    assert len(root_node.children) == 1
    assert root_node.children[0].direct_items == 2
    assert root_node.children[0].total_items == 2


def test_full_tree_with_counts_on_empty_database(db):
    assert get_full_tree_with_counts(db, item_model=Poster) == []


def test_unfiled_posters_are_not_double_counted_in_tree(db):
    """A poster with folder_id=None must never appear under any node's
    count - it belongs at the archive root, outside the tree entirely."""
    create_folder(db, name="Root", parent_id=None, created_by="admin")
    db.add(Poster(poster_title="Unfiled", dropbox_url="https://www.dropbox.com/u", folder_id=None))
    db.commit()

    tree = get_full_tree_with_counts(db, item_model=Poster)
    assert tree[0].total_items == 0
