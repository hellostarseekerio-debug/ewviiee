"""Per-user favorites - reusable across resource types (see
app/core/models.py's StarredItem docstring for why this is one small side
table rather than an `is_starred` column repeated on every resource).
Personal data: any authenticated user may star/unstar/list their own,
never someone else's - there is no "star on behalf of" or "list all users'
stars" endpoint here."""
# Deliberately no `from __future__ import annotations` here: this module
# mixes `@limiter.limit(...)` (slowapi) with body-model params, and
# slowapi's wrapper doesn't preserve this module's globals for resolving
# string annotations - FastAPI then fails at startup trying to resolve an
# unresolved ForwardRef for the body model's type. See posters.py's
# top-of-file comment for the original instance of this; same fix here.
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.rate_limit import limiter
from app.api.schemas import StarRequest, StarredItemOut
from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import StarredItem, User

router = APIRouter(prefix="/api/starred", tags=["starred"])


@router.get("", response_model=list[StarredItemOut])
def list_my_starred(
    resource_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(StarredItem).filter(StarredItem.user_id == current_user.id)
    if resource_type:
        query = query.filter(StarredItem.resource_type == resource_type)
    return query.order_by(StarredItem.created_at.desc()).all()


@router.post("", response_model=StarredItemOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_default)
def star_item(
    request: Request,
    payload: StarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(StarredItem)
        .filter(
            StarredItem.user_id == current_user.id,
            StarredItem.resource_type == payload.resource_type,
            StarredItem.resource_id == payload.resource_id,
        )
        .first()
    )
    if existing:
        return existing  # idempotent - starring an already-starred item is a no-op, not a conflict
    item = StarredItem(user_id=current_user.id, resource_type=payload.resource_type, resource_id=payload.resource_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{resource_type}/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().rate_limit_default)
def unstar_item(
    request: Request,
    resource_type: str,
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(StarredItem).filter(
        StarredItem.user_id == current_user.id,
        StarredItem.resource_type == resource_type,
        StarredItem.resource_id == resource_id,
    ).delete(synchronize_session=False)
    db.commit()
