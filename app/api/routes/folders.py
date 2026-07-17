"""Generic folder endpoints - app/folders/service.py backs these, and they
know nothing about Posters specifically. `resource_type` (default
"poster") selects which resource's rows are counted/relocated for
stats/delete, via app/folders/registry.py; new resources add support by
registering there, not by adding new routes here.

Security: create/rename/move require Editor+ (matches Poster/Document
create-edit convention elsewhere in the API); delete requires Admin+
(matches every other hard-delete in this API). Every mutating action is
audit-logged.
"""
# Deliberately no `from __future__ import annotations` here: this module
# mixes `@limiter.limit(...)` (slowapi) with body-model params, and
# slowapi's wrapper doesn't preserve this module's globals for resolving
# string annotations - FastAPI then fails at startup trying to resolve an
# unresolved ForwardRef for the body model's type. See posters.py's
# top-of-file comment for the original instance of this; same fix here.
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.api.rate_limit import limiter
from app.api.schemas import (
    FolderCreateRequest,
    FolderDetailOut,
    FolderMoveRequest,
    FolderOut,
    FolderRenameRequest,
    FolderStatsOut,
    FolderTreeNodeOut,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging_config import record_audit
from app.core.models import UserRole
from app.folders.registry import UnknownResourceTypeError, resolve_resource_model
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
)

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _resource_model(resource_type: str):
    try:
        return resolve_resource_model(resource_type)
    except UnknownResourceTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/tree", response_model=list[FolderTreeNodeOut])
def get_folder_tree(
    resource_type: str = Query(default="poster"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    model = _resource_model(resource_type)
    return get_full_tree_with_counts(db, item_model=model)


@router.get("", response_model=list[FolderOut])
def list_folder_children(
    parent_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if parent_id:
        get_folder_or_raise(db, parent_id)  # 404s cleanly instead of silently returning []
    return list_children(db, parent_id)


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_default)
def create_new_folder(
    request: Request,
    payload: FolderCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    try:
        folder = create_folder(db, name=payload.name, parent_id=payload.parent_id, created_by=current_user.username)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except FolderError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit(actor=current_user.username, action="folder_created", resource_type="folder", resource_id=folder.id)
    return folder


@router.get("/{folder_id}", response_model=FolderDetailOut)
def get_folder_detail(
    folder_id: str,
    resource_type: str = Query(default="poster"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    model = _resource_model(resource_type)
    try:
        folder = get_folder_or_raise(db, folder_id)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return FolderDetailOut(
        folder=folder,
        breadcrumbs=get_breadcrumbs(db, folder),
        stats=FolderStatsOut(**vars(get_folder_stats(db, folder, item_model=model))),
        children=list_children(db, folder.id),
    )


@router.patch("/{folder_id}", response_model=FolderOut)
@limiter.limit(lambda: get_settings().rate_limit_default)
def rename_existing_folder(
    request: Request,
    folder_id: str,
    payload: FolderRenameRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    try:
        folder = rename_folder(db, folder_id, payload.name)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except FolderError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit(actor=current_user.username, action="folder_renamed", resource_type="folder", resource_id=folder.id)
    return folder


@router.post("/{folder_id}/move", response_model=FolderOut)
@limiter.limit(lambda: get_settings().rate_limit_default)
def move_existing_folder(
    request: Request,
    folder_id: str,
    payload: FolderMoveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.EDITOR)),
):
    try:
        folder = move_folder(db, folder_id, payload.parent_id)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except FolderError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit(
        actor=current_user.username, action="folder_moved", resource_type="folder", resource_id=folder.id,
        detail={"new_parent_id": payload.parent_id},
    )
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().rate_limit_default)
def delete_existing_folder(
    request: Request,
    folder_id: str,
    resource_type: str = Query(default="poster"),
    recursive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    model = _resource_model(resource_type)
    try:
        delete_folder(db, folder_id, item_model=model, recursive=recursive)
    except FolderNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except FolderError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    record_audit(
        actor=current_user.username, action="folder_deleted", resource_type="folder", resource_id=folder_id,
        detail={"recursive": recursive},
    )
