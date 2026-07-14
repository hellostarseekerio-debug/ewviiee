"""Learned field corrections: the parser's self-improvement loop.

The concrete problem this solves: the parser resolves an estate name
(via config/rules/estates.yaml, or the regex suffix fallback when the
estate isn't in that file yet) but has no district for it. Rather than
requiring a config/YAML edit and a deploy every time an unlisted estate
shows up, a member of staff corrects the district once on that one poster
record, and this module remembers it - so every future record mentioning
that same estate name gets the district auto-filled from then on, no
code change or redeploy required.

Deliberately a small, generic key/value table (app.core.models.
LearnedFieldCorrection) rather than writing back into the YAML files
directly: YAML edits are a deliberate, reviewed, deployed change (see
that file's own docstring on why politicians/routes/templates are left
empty rather than guessed); a single staff correction on one record is a
much lower-stakes, immediate signal that shouldn't require a deploy to
take effect, and this table is exactly that - fast-changing, per-office,
never mistaken for the curated reference data in YAML.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.models import LearnedFieldCorrection


def record_correction(
    db: Session,
    *,
    key_type: str,
    key_value: str,
    field: str,
    value: str,
    corrected_by: str | None,
) -> None:
    """Remembers `field=value` for the next time `key_value` (of
    `key_type`) is seen - e.g. key_type="estate_name", key_value="富蝶邨",
    field="district", value="大埔". Upserts: a later correction for the
    same key/field replaces the earlier one (staff fixing their own past
    mistake), never leaves both around."""
    existing = (
        db.query(LearnedFieldCorrection)
        .filter(
            LearnedFieldCorrection.key_type == key_type,
            LearnedFieldCorrection.key_value == key_value,
            LearnedFieldCorrection.field == field,
        )
        .first()
    )
    if existing:
        existing.value = value
        existing.corrected_by = corrected_by
    else:
        db.add(
            LearnedFieldCorrection(
                key_type=key_type, key_value=key_value, field=field, value=value, corrected_by=corrected_by
            )
        )


def lookup_correction(db: Session, *, key_type: str, key_value: str, field: str) -> str | None:
    row = (
        db.query(LearnedFieldCorrection)
        .filter(
            LearnedFieldCorrection.key_type == key_type,
            LearnedFieldCorrection.key_value == key_value,
            LearnedFieldCorrection.field == field,
        )
        .first()
    )
    return row.value if row else None
