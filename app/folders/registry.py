"""Maps a `resource_type` string (as used in API query params/bodies) to
the SQLAlchemy model it names, for the generic folder/starred-item
services. New resources (Document, ...) opt into folders/favorites by
adding one line here plus a `folder_id` column on their own model - see
app/folders/service.py's module docstring for the full contract."""
from __future__ import annotations

from app.core.models import Poster

RESOURCE_MODELS: dict[str, type] = {
    "poster": Poster,
}


class UnknownResourceTypeError(ValueError):
    pass


def resolve_resource_model(resource_type: str) -> type:
    model = RESOURCE_MODELS.get(resource_type)
    if model is None:
        valid = ", ".join(sorted(RESOURCE_MODELS))
        raise UnknownResourceTypeError(f"Unknown resource_type '{resource_type}' (valid: {valid})")
    return model
