"""AI fallback for poster metadata extraction - invoked by
app/posters/parser.py only when rule-based extraction (regex segments +
RuleEngine's district/estate alias/fuzzy/AI resolution) still leaves a
record's title AND both district/estate unresolved. Matches the
platform's "deterministic first" policy: this is the *last* resort, never
the first attempt, and every call result is cached so the same source
text is never sent to an AI provider twice.

Caching is keyed by a hash of the exact source text (not the individual
fields), since the fallback is always invoked with the same "extract
title/district/estate/poster_type from this whole block" request - one
cache row per distinct block, not per field.
"""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.ai.factory import get_guarded_ai_provider
from app.core.logging_config import get_logger
from app.core.models import MetadataExtractionCache

logger = get_logger("posters.ai_fallback")

_SCHEMA = {
    "title": "The poster/notice's title or subject, in its original language",
    "district": "The Hong Kong district this poster concerns, if any",
    "estate": "The housing estate this poster concerns, if any",
    "poster_type": "A short category for this poster (e.g. notice, transport, event)",
}

_CONTEXT = (
    "This text is one record from a Hong Kong Legislative Council office's "
    "Poster Archive import. Rule-based parsing could not confidently "
    "determine some fields - extract what you can directly from the text, "
    "never invent information that isn't present."
)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_ai_extracted_fields(db: Session, text: str) -> dict | None:
    """Returns a dict with any of `title`/`district`/`estate`/`poster_type`
    the AI provider could extract, or None if no AI provider is available
    (no cloud AI configured/allowed and no local provider reachable) or
    the call failed. Never raises."""
    text_hash = _text_hash(text)
    cached = db.get(MetadataExtractionCache, text_hash)
    if cached is not None:
        return cached.result

    provider = get_guarded_ai_provider()
    if provider is None:
        return None

    try:
        response = provider.extract_fields(text, _SCHEMA, context=_CONTEXT)
    except Exception as exc:
        logger.warning("poster_ai_fallback_failed", error=str(exc))
        return None

    result = {k: v for k, v in (response.raw or {}).items() if k in _SCHEMA and v}
    if not result:
        return None

    entry = MetadataExtractionCache(text_hash=text_hash, result=result)
    db.merge(entry)
    db.flush()
    return result
