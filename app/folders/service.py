"""Generic, resource-agnostic folder engine: nested folders of unlimited
depth with create/rename/move/delete, breadcrumbs, subtree lookup, and
item-counting statistics.

This module has no idea Posters (or, later, Documents) exist - every
function that needs to know "how many things live in this folder" or
"where should contained items go when this folder is deleted" takes the
resource's SQLAlchemy model as a plain parameter (`item_model`), which
must expose a `.folder_id` column and a `.id` column. That's the entire
contract a resource needs to satisfy to plug into the folder system - see
app/folders/registry.py for how a resource_type string maps to its model,
and app/posters/status.py/app/core/models.py's Poster.folder_id for the
first (and, for now, only) resource that uses it.

Path model: `Folder.path` is a materialized path of ancestor ids
(root-to-self, "/"-joined, including the folder's own id). This keeps two
operations that would otherwise need a recursive CTE down to a single
indexed query:
  - breadcrumbs: split `path` on "/", one `WHERE id IN (...)` lookup.
  - subtree (this folder + every descendant, at any depth): `path LIKE
    '{folder.path}/%'` (plus the folder itself).
The tradeoff is that moving a folder must rewrite the `path`/`depth` of
every descendant (see move_folder) - an O(subtree size) operation, but
folder counts are tiny relative to the tens-of-thousands of *items* they
contain, so this is the right side of that tradeoff for this system.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.models import Folder


class FolderError(ValueError):
    """Raised for invalid folder operations (not found, duplicate sibling
    name, moving/deleting into an inconsistent state). Callers turn this
    into an HTTP 404/409 - never a 500, since every case here is a normal,
    user-facing outcome of an invalid request."""


class FolderNotFoundError(FolderError):
    pass


def get_folder_or_raise(db: Session, folder_id: str) -> Folder:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise FolderNotFoundError(f"Folder '{folder_id}' not found")
    return folder


def _build_path(parent: Folder | None, own_id: str) -> str:
    return f"{parent.path}/{own_id}" if parent is not None else own_id


def _sibling_conflict(db: Session, parent_id: str | None, name: str, *, exclude_id: str | None = None) -> bool:
    query = db.query(Folder.id).filter(
        Folder.parent_id == parent_id, func.lower(Folder.name) == name.strip().lower()
    )
    if exclude_id:
        query = query.filter(Folder.id != exclude_id)
    return query.first() is not None


def create_folder(db: Session, *, name: str, parent_id: str | None, created_by: str | None) -> Folder:
    name = name.strip()
    if not name:
        raise FolderError("Folder name cannot be empty")
    parent = get_folder_or_raise(db, parent_id) if parent_id else None
    if _sibling_conflict(db, parent_id, name):
        raise FolderError(f"A folder named '{name}' already exists here")

    folder = Folder(
        name=name,
        parent_id=parent_id,
        depth=(parent.depth + 1) if parent else 0,
        path="",  # placeholder until the id exists (see below)
        created_by=created_by,
    )
    db.add(folder)
    db.flush()  # assigns folder.id without committing, so path can include it
    folder.path = _build_path(parent, folder.id)
    db.commit()
    db.refresh(folder)
    return folder


def rename_folder(db: Session, folder_id: str, new_name: str) -> Folder:
    folder = get_folder_or_raise(db, folder_id)
    new_name = new_name.strip()
    if not new_name:
        raise FolderError("Folder name cannot be empty")
    if _sibling_conflict(db, folder.parent_id, new_name, exclude_id=folder.id):
        raise FolderError(f"A folder named '{new_name}' already exists here")
    folder.name = new_name
    db.commit()
    db.refresh(folder)
    return folder


def _is_own_subtree(candidate_path: str, folder: Folder) -> bool:
    return candidate_path == folder.path or candidate_path.startswith(folder.path + "/")


def move_folder(db: Session, folder_id: str, new_parent_id: str | None) -> Folder:
    """Reparents a folder, rewriting the materialized path/depth of every
    descendant so subtree queries keep working immediately after the move -
    see the module docstring for why the path model makes this necessary."""
    folder = get_folder_or_raise(db, folder_id)
    if new_parent_id == folder.parent_id:
        return folder
    if new_parent_id == folder.id:
        raise FolderError("A folder cannot be moved into itself")

    new_parent = get_folder_or_raise(db, new_parent_id) if new_parent_id else None
    if new_parent is not None and _is_own_subtree(new_parent.path, folder):
        raise FolderError("Cannot move a folder into its own subtree")
    if _sibling_conflict(db, new_parent_id, folder.name, exclude_id=folder.id):
        raise FolderError(f"A folder named '{folder.name}' already exists in the destination")

    old_path = folder.path
    new_depth = (new_parent.depth + 1) if new_parent else 0
    new_path = _build_path(new_parent, folder.id)
    depth_delta = new_depth - folder.depth

    descendants = db.query(Folder).filter(Folder.path.like(f"{old_path}/%")).all()
    for descendant in descendants:
        descendant.path = new_path + descendant.path[len(old_path):]
        descendant.depth += depth_delta

    folder.parent_id = new_parent_id
    folder.path = new_path
    folder.depth = new_depth
    db.commit()
    db.refresh(folder)
    return folder


def list_children(db: Session, parent_id: str | None) -> list[Folder]:
    return db.query(Folder).filter(Folder.parent_id == parent_id).order_by(Folder.name.asc()).all()


def get_breadcrumbs(db: Session, folder: Folder) -> list[Folder]:
    """Root-to-self ordered list of every ancestor, including `folder`
    itself - a single indexed lookup via the materialized path, not a
    recursive walk."""
    ancestor_ids = folder.path.split("/")
    rows = db.query(Folder).filter(Folder.id.in_(ancestor_ids)).all()
    by_id = {row.id: row for row in rows}
    return [by_id[i] for i in ancestor_ids if i in by_id]


def subtree_folder_ids(db: Session, folder: Folder, *, include_self: bool = True) -> list[str]:
    rows = db.query(Folder.id).filter(Folder.path.like(f"{folder.path}/%")).all()
    ids = [row[0] for row in rows]
    if include_self:
        ids.append(folder.id)
    return ids


def delete_folder(db: Session, folder_id: str, *, item_model, recursive: bool = False) -> None:
    """Deletes a folder (and, if `recursive`, its entire subtree). Contained
    items are never deleted - they're detached (folder_id set to NULL,
    i.e. "unfiled") since a folder organizes records, it doesn't own their
    lifecycle. `item_model` is the resource's SQLAlchemy model (e.g.
    Poster) - see the module docstring."""
    folder = get_folder_or_raise(db, folder_id)
    subtree_ids = subtree_folder_ids(db, folder, include_self=True)
    has_subfolders = len(subtree_ids) > 1
    has_items = db.query(item_model.id).filter(item_model.folder_id.in_(subtree_ids)).first() is not None

    if (has_subfolders or has_items) and not recursive:
        raise FolderError(
            "Folder is not empty - pass recursive=true to delete it along with its contents "
            "(contained records are unfiled, never deleted)"
        )

    if has_items:
        db.query(item_model).filter(item_model.folder_id.in_(subtree_ids)).update(
            {"folder_id": None}, synchronize_session="fetch"
        )
    # synchronize_session="fetch" (not False): keeps the ORM session's
    # identity map consistent with the delete, so a caller that looks the
    # folder up again in the same session afterwards cleanly gets "not
    # found" rather than SQLAlchemy trying to refresh a now-expired,
    # already-deleted instance and raising ObjectDeletedError.
    db.query(Folder).filter(Folder.id.in_(subtree_ids)).delete(synchronize_session="fetch")
    db.commit()


@dataclass
class FolderStats:
    folder_id: str
    direct_subfolders: int
    direct_items: int
    total_subfolders: int
    total_items: int


def get_folder_stats(db: Session, folder: Folder, *, item_model) -> FolderStats:
    subtree_ids = subtree_folder_ids(db, folder, include_self=True)
    direct_subfolders = db.query(Folder).filter(Folder.parent_id == folder.id).count()
    direct_items = db.query(item_model).filter(item_model.folder_id == folder.id).count()
    total_items = db.query(item_model).filter(item_model.folder_id.in_(subtree_ids)).count()
    return FolderStats(
        folder_id=folder.id,
        direct_subfolders=direct_subfolders,
        direct_items=direct_items,
        total_subfolders=len(subtree_ids) - 1,
        total_items=total_items,
    )


@dataclass
class FolderTreeNode:
    id: str
    name: str
    parent_id: str | None
    depth: int
    direct_items: int
    total_items: int
    children: list["FolderTreeNode"]


def get_full_tree_with_counts(db: Session, *, item_model) -> list[FolderTreeNode]:
    """The whole folder tree in one pass, with per-folder item counts -
    two queries total (all folders, and a single grouped count over
    `item_model`), regardless of how many items exist. Folder counts stay
    small even in a very large archive (tens of thousands of items still
    means, realistically, hundreds of folders, not tens of thousands), so
    loading every folder row at once and building the tree in Python is
    the simplest approach that's still fast - the thing that must scale to
    50,000+ rows is the *item* count query, which the database computes
    via its own index, never by this code loading every item."""
    folders = db.query(Folder).order_by(Folder.depth.asc(), Folder.name.asc()).all()
    direct_counts = dict(
        db.query(item_model.folder_id, func.count(item_model.id))
        .filter(item_model.folder_id.isnot(None))
        .group_by(item_model.folder_id)
        .all()
    )

    children_by_parent: dict[str | None, list[Folder]] = {}
    for folder in folders:
        children_by_parent.setdefault(folder.parent_id, []).append(folder)

    def build(parent_id: str | None) -> list[FolderTreeNode]:
        nodes = []
        for folder in children_by_parent.get(parent_id, []):
            children = build(folder.id)
            direct = direct_counts.get(folder.id, 0)
            total = direct + sum(child.total_items for child in children)
            nodes.append(
                FolderTreeNode(
                    id=folder.id,
                    name=folder.name,
                    parent_id=folder.parent_id,
                    depth=folder.depth,
                    direct_items=direct,
                    total_items=total,
                    children=children,
                )
            )
        return nodes

    return build(None)
