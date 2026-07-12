"""Parses a large pasted block of text (one or more poster/notice records,
each a title line plus a Dropbox link) into structured records for the
Poster Archive - see docs/api.md's "Poster Archive" section for the field
reference and app/api/routes/posters.py for how this is used.

Deliberately deterministic (regex + the existing YAML-driven district/
estate alias/fuzzy matching in app.rules.engine), not AI-based: this
mirrors the platform's "deterministic first" policy used everywhere else
(see app/rules/engine.py's module docstring), and staff pasting hundreds
of records at once need parsing to be fast, free, and not dependent on an
AI provider being configured.

Every field extractor is independent and wrapped so it can never raise -
if a field can't be confidently extracted, it is left None (per the
requirement: "leave it blank instead of crashing"). A block with no
Dropbox link at all is skipped entirely (nothing to import), everything
else degrades field-by-field instead of discarding the whole record.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.rules.engine import RuleEngine

DROPBOX_URL_RE = re.compile(r"https?://(?:www\.)?dropbox\.com/\S+", re.IGNORECASE)

# 20260707 / 2026-07-07 / 2026/07/07 / 2026年7月7日 - the four separator
# styles actually seen in office-supplied text, in one pattern.
_DATE_RE = re.compile(r"(20\d{2})[-/年]?(\d{1,2})[-/月]?(\d{1,2})日?")

# 【...】 and 「...」 are the two bracket styles used for poster titles in
# the source material; plain [...] as a common ASCII fallback.
_BRACKET_RE = re.compile(r"[【\[](.+?)[】\]]|「(.+?)」")

# Hong Kong bus/minibus route codes: 1-3 digits, optional 1-2 trailing
# letters (73H, 290A, 1). Longer digit runs are dates/phone numbers/IDs,
# not routes - excluded explicitly below rather than by the regex itself,
# since a 4-digit token still needs to be found before it can be rejected.
_ROUTE_RE = re.compile(r"\b(\d{1,4}[A-Z]{0,2})\b")

_POSTER_TYPE_KEYWORDS = {
    "海報": "poster",
    "海报": "poster",
    "通告": "notice",
    "公告": "announcement",
    "單張": "flyer",
    "单张": "flyer",
}

_STOPWORDS = {"", "-", "來往", "来往", "路線", "路线"}


@dataclass
class ParsedPoster:
    """One record extracted from a pasted block. `dropbox_url` and
    `source_text` are always populated (a block is only ever turned into a
    ParsedPoster once a Dropbox link is confirmed present) - every other
    field is best-effort and may be None."""

    dropbox_url: str
    source_text: str
    district: str | None = None
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    document_date: datetime | None = None
    language: str | None = None
    keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _extract_date(text: str) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None  # e.g. "2026-13-40" - not a real date, leave blank


def _extract_route(text: str) -> str | None:
    for match in _ROUTE_RE.finditer(text):
        token = match.group(1)
        if token.isdigit() and len(token) > 3:
            continue  # a bare 4+ digit run is a date/id, not a route code
        return token
    return None


def _extract_title(text: str) -> str | None:
    match = _BRACKET_RE.search(text)
    if match:
        title = (match.group(1) or match.group(2) or "").strip()
        return title or None
    stripped = " ".join(text.split())
    return stripped or None


def _detect_language(text: str) -> str | None:
    has_cjk = bool(re.search(r"[一-鿿]", text))
    has_latin = bool(re.search(r"[A-Za-z]{2,}", text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return None


def _extract_poster_type(text: str) -> str | None:
    for keyword, poster_type in _POSTER_TYPE_KEYWORDS.items():
        if keyword in text:
            return poster_type
    return None


def _extract_keywords(text: str, already_extracted: list[str]) -> list[str]:
    remainder = _BRACKET_RE.sub(" ", text)
    for token in already_extracted:
        remainder = remainder.replace(token, " ")
    parts = re.split(r"[\-–—_/,，、\s]+", remainder)
    keywords: list[str] = []
    for part in parts:
        cleaned = part.strip("【】「」[]()（）")
        if cleaned and cleaned not in _STOPWORDS and cleaned not in keywords and len(cleaned) > 1:
            keywords.append(cleaned)
    return keywords[:12]


def split_into_blocks(raw_text: str) -> list[str]:
    """Splits a large pasted blob into one chunk per record: everything up
    to and including its Dropbox link. A run of blank lines after a
    completed record (one containing a link) starts the next one. Text
    with no Dropbox link anywhere is returned as zero blocks - there is
    nothing importable in it, which is a normal, non-error outcome."""
    if not raw_text or not raw_text.strip():
        return []

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in raw_text.splitlines():
        if not line.strip():
            if current and any(DROPBOX_URL_RE.search(existing) for existing in current):
                blocks.append(current)
                current = []
            continue
        current.append(line)
        if DROPBOX_URL_RE.search(line):
            blocks.append(current)
            current = []
    if current and any(DROPBOX_URL_RE.search(existing) for existing in current):
        blocks.append(current)
    return ["\n".join(block) for block in blocks]


def parse_block(block: str, rule_engine: RuleEngine | None) -> ParsedPoster | None:
    """Parses one block into a ParsedPoster, or None if it has no Dropbox
    link (nothing to import). Every other field is extracted independently
    and defensively - one field's extractor raising never prevents the
    others from populating."""
    url_match = DROPBOX_URL_RE.search(block)
    if url_match is None:
        return None

    dropbox_url = url_match.group(0).rstrip(").,;、")
    text_only = " ".join(DROPBOX_URL_RE.sub(" ", block).split())

    parsed = ParsedPoster(dropbox_url=dropbox_url, source_text=block.strip())

    try:
        parsed.document_date = _extract_date(text_only)
    except Exception:
        parsed.warnings.append("date_extraction_failed")

    try:
        parsed.route_number = _extract_route(text_only)
    except Exception:
        parsed.warnings.append("route_extraction_failed")

    try:
        parsed.poster_type = _extract_poster_type(text_only)
    except Exception:
        parsed.warnings.append("poster_type_extraction_failed")

    try:
        parsed.language = _detect_language(text_only)
    except Exception:
        parsed.warnings.append("language_detection_failed")

    resolved_district_id = None
    if rule_engine is not None:
        try:
            district = rule_engine.resolve_district(text_only)
            if district is not None:
                parsed.district = district.name
                resolved_district_id = district.id
        except Exception:
            parsed.warnings.append("district_resolution_failed")

        try:
            estate = rule_engine.resolve_estate(text_only, district_id=resolved_district_id)
            if estate is not None:
                parsed.estate = estate.name
        except Exception:
            parsed.warnings.append("estate_resolution_failed")

    try:
        parsed.poster_title = _extract_title(text_only)
    except Exception:
        parsed.warnings.append("title_extraction_failed")

    try:
        already = [v for v in (parsed.district, parsed.estate, parsed.route_number) if v]
        parsed.keywords = _extract_keywords(text_only, already)
    except Exception:
        parsed.warnings.append("keyword_extraction_failed")

    return parsed


def parse_poster_text(raw_text: str, rule_engine: RuleEngine | None = None) -> list[ParsedPoster]:
    """Top-level entry point used by POST /api/posters/import. Splits a
    large pasted blob into records and parses each - never raises for
    malformed/inconsistent input; a block with no Dropbox link is silently
    skipped, and every field within a parsed block degrades independently.
    """
    return [
        parsed
        for block in split_into_blocks(raw_text)
        if (parsed := parse_block(block, rule_engine)) is not None
    ]
