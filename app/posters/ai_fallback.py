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


def ai_infer_district_for_estate(db: Session, estate_name: str, district_names: list[str]) -> str | None:
    """Layer 3 of district detection (see app/posters/parser.py's
    docstring): the estate resolved (via config/rules/estates.yaml or the
    regex suffix fallback) but isn't in the curated YAML and no staff
    correction has been recorded for it yet (app.posters.corrections) -
    ask the AI provider which of the 18 HK districts it's in. Cached the
    same way as get_ai_extracted_fields (keyed on the estate name itself,
    not the whole block, since this is a much narrower question with a
    stable, reusable answer independent of which record asked it)."""
    if not district_names:
        return None
    text_hash = _text_hash(f"estate_district::{estate_name}")
    cached = db.get(MetadataExtractionCache, text_hash)
    if cached is not None:
        return cached.result.get("district")

    provider = get_guarded_ai_provider()
    if provider is None:
        return None

    try:
        response = provider.classify(
            estate_name,
            district_names,
            context="Identify the Hong Kong district this housing estate is located in.",
        )
    except Exception as exc:
        logger.warning("poster_ai_district_fallback_failed", estate=estate_name, error=str(exc))
        return None

    answer = (response.text or "").strip()
    if answer not in district_names:
        return None

    entry = MetadataExtractionCache(text_hash=text_hash, result={"district": answer})
    db.merge(entry)
    db.flush()
    return answer
