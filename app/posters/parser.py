"""Parses a large pasted block of text (one or more poster/notice records,
each a title line plus a Dropbox link) into structured records for the
Poster Archive - see docs/api.md's "Poster Archive" section for the field
reference and app/api/routes/posters.py for how this is used.

Rule-based first (regex + the YAML-driven district/estate alias/fuzzy
matching in app.rules.engine, richened by app.posters.estates'
EstateMetadataService), with an AI fallback (app.posters.ai_fallback)
invoked only when rule-based extraction still leaves both the title and
district/estate unresolved - the platform's "deterministic first" policy
applied one level deeper than before: AI is the last resort, not the
first attempt, and every AI call result is cached so the same source text
is never sent to a provider twice.

Every field extractor is independent and wrapped so it can never raise -
if a field can't be confidently extracted, it is left None (per the
requirement: "leave it blank instead of crashing"). A block with no
Dropbox link at all is skipped entirely (nothing to import), everything
else degrades field-by-field instead of discarding the whole record.

Segment-based title extraction: the metadata line format actually used in
practice is hyphen-delimited fields - "<date>-<poster type>-<title>-
<route>-<estate description>" (e.g. "20260707-海報-好消息-73H-愉翠苑來往大埔
富蝶邨") - so `_extract_title` splits on hyphen variants and drops any
segment fully explained by another field this parser extracts elsewhere
(a date, an exact poster-type keyword, a route code, or a route "from A
to B" description). What's left is the real title, instead of the whole
raw line - dates, types, routes and all - being stored as if it were the
title. Every field this module returns is also given a confidence
(0.0-1.0) and a source ("regex" | "rule_engine" | "ai" | "default") via
`ParsedPoster.field_confidence`/`field_sources`, so a low-confidence field
can be flagged in the UI without the whole record being treated as
unreliable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.posters.estates import EstateMetadataService
from app.rules.engine import RuleEngine

DROPBOX_URL_RE = re.compile(r"https?://(?:www\.)?dropbox\.com/\S+", re.IGNORECASE)

# 20260707 / 2026-07-07 / 2026/07/07 / 2026年7月7日 - the four separator
# styles actually seen in office-supplied text, in one pattern.
_DATE_RE = re.compile(r"(20\d{2})[-/年]?(\d{1,2})[-/月]?(\d{1,2})日?")

# 【...】 and 「...」 are the two bracket styles used for poster titles in
# the source material; plain [...] as a common ASCII fallback.
_BRACKET_RE = re.compile(r"[【\[](.+?)[】\]]|「(.+?)」")

# Hong Kong bus/minibus route codes: 1-4 digits, with an optional 1-2
# letter prefix (airport/cross-harbour/night routes like A41, E21, N281)
# and/or suffix (73H, 290A). Longer bare digit runs are dates/phone
# numbers/ids, not routes - excluded explicitly in _extract_route rather
# than by the regex itself, since a 4+ digit run still needs to be found
# before it can be rejected.
_ROUTE_RE = re.compile(r"\b([A-Z]{0,2}\d{1,4}[A-Z]{0,2})\b")

_POSTER_TYPE_KEYWORDS = {
    # More specific categories checked before their generic counterparts
    # (dict order is preserved in Python 3.7+, and _extract_poster_type
    # returns the first keyword found) - "交通通告" must win over the bare
    # "通告" it contains, or every transport notice would be miscategorized
    # as a generic notice.
    "交通通告": "transport_notice",
    "运输通告": "transport_notice",
    "運輸通告": "transport_notice",
    "房屋通告": "housing_notice",
    "屋邨通告": "housing_notice",
    "屋苑通告": "housing_notice",
    "政府公告": "government_announcement",
    "交通改道": "traffic_diversion",
    "跨境": "cross_border",
    "工程": "works",
    "環保": "environmental",
    "环保": "environmental",
    "法律": "legal",
    "公共服務": "public_service",
    "公共服务": "public_service",
    "寵物": "pets",
    "宠物": "pets",
    "活動": "event",
    "活动": "event",
    "海報": "poster",
    "海报": "poster",
    # Only matched by exact-segment classification (see
    # _extract_poster_type_from_segments) - a segment that's also a valid
    # title candidate elsewhere ("好消息" as a record's actual subject, not
    # its category marker) still wins as title whenever an earlier segment
    # (e.g. "海報") already claimed the type slot; this key only fires when
    # "好消息" is the ONLY type-like segment present.
    "好消息": "good_news",
    "好消息通告": "good_news",
    "政策": "policy",
    "社區": "community",
    "社区": "community",
    "宣傳": "campaign",
    "宣传": "campaign",
    "通告": "notice",
    "通知": "notice",
    "公告": "announcement",
    "單張": "flyer",
    "单张": "flyer",
}

# Topical keywords worth surfacing regardless of where in the text they
# appear (unlike _POSTER_TYPE_KEYWORDS, these are not mutually exclusive -
# a poster about a stray-dog feeding ban at a restaurant district might
# reasonably carry several of these at once). Matched in addition to,
# never instead of, the leftover-token keyword extraction below.
_TOPIC_KEYWORDS = {
    "狗": "狗隻", "犬": "狗隻",
    "貓": "貓隻", "猫": "猫只",
    "寵物": "寵物", "宠物": "宠物",
    "食肆": "食肆", "餐廳": "餐廳", "餐厅": "餐厅",
    "政府": "政府",
    "工程": "工程",
    "交通": "交通",
    "巴士": "巴士",
    "小巴": "小巴",
    "環保": "環保", "环保": "环保",
    "法律": "法律",
    "屋邨": "屋邨",
    "屋苑": "屋苑",
}

# Common Hong Kong government department names/abbreviations, matched as a
# best-effort substring check - same "deterministic first" spirit as the
# district/estate suffix fallbacks above, not an exhaustive directory.
_GOV_DEPARTMENT_KEYWORDS = {
    "民政事務處": "民政事務處",
    "民政事务处": "民政事务处",
    "房屋署": "房屋署",
    "運輸署": "運輸署",
    "运输署": "运输署",
    "康樂及文化事務署": "康樂及文化事務署",
    "康乐及文化事务署": "康乐及文化事务署",
    "食物環境衞生署": "食物環境衞生署",
    "食物环境卫生署": "食物环境卫生署",
    "地政總署": "地政總署",
    "地政总署": "地政总署",
    "警務處": "警務處",
    "警务处": "警务处",
    "立法會": "立法會",
    "立法会": "立法会",
}

# "v2" / "V2.1" / "第2版" / "版2" - the version-marker styles actually seen
# in poster filenames/titles, mirroring app/plugins/housing_estate_poster/
# plugin.py's `_TITLE_PATTERN` (kept independent since that one also
# captures a title group this module extracts separately).
_VERSION_RE = re.compile(r"(?:[vV](\d+(?:\.\d+)?))|(?:第\s*(\d+)\s*版)|(?:版\s*(\d+))")

_STOPWORDS = {"", "-", "來往", "来往", "路線", "路线"}

# A route-number match must be at least 2 characters (digits+optional
# letters) to be trusted - a bare single digit ("2") is far more often a
# stray version/page number than a real route, per real-world false
# positives seen in production pastes (e.g. "版 2" tokenizing as route "2"
# once whitespace separates it from "版"). Genuine single-digit minibus
# routes exist but are rare enough that this tradeoff favors not
# mis-tagging a version number as a route.
_MIN_ROUTE_LENGTH = 2

# Zero-width/invisible characters that survive copy-paste from web pages,
# Notion, Word, etc. (zero-width space, ZWNJ/ZWJ, word joiner, BOM). A
# "blank" separator line carrying only one of these looks empty to a human
# but is non-empty to str.strip(), which used to make the block splitter
# treat it as real content and merge unrelated records together.
_INVISIBLE_RE = re.compile(r"[​‌‍⁠﻿]")

# The 18 Hong Kong districts' Chinese names, used only to strip a leading
# "<district> " token off an otherwise-plain title (e.g. "沙田
# 20260707-..." -> "20260707-..."). Kept independent of the YAML-driven
# RuleEngine (config/rules/districts.yaml) so title cleanup still works
# even when no rule engine is wired in, or the paste uses a district name
# the engine doesn't recognise.
_HK_DISTRICTS_ZH = [
    "中西區", "中西区", "灣仔", "湾仔", "東區", "东区", "南區", "南区",
    "油尖旺", "深水埗", "九龍城", "九龙城", "黃大仙", "黄大仙", "觀塘", "观塘",
    "葵青", "荃灣", "荃湾", "屯門", "屯门", "元朗", "北區", "北区", "大埔",
    "沙田", "西貢", "西贡", "離島", "离岛",
]

# Common suffixes for Hong Kong housing estate / building names, used as a
# last-resort fallback to find an estate name that isn't in the curated
# config/rules/estates.yaml list (and no AI provider is configured to fall
# back to). Deliberately only a suffix heuristic - never treated as more
# authoritative than a real RuleEngine alias/fuzzy match.
#
# The prefix quantifier is non-greedy ({2,8}?), not {2,8}: a greedy prefix
# backtracks from the *longest* possible match, so on text like "華明邨居民
# 請注意" (Wah Ming Estate *residents*, please note...) it walks past the
# real "華明邨" suffix match and keeps extending until it hits the next
# suffix character it can reach - here "居" from "居民" - returning the
# corrupted estate name "華明邨居" instead of "華明邨". Every one of these
# suffix characters (居/城/坊/村/苑/邨...) also opens extremely common
# unrelated words (居民 "residents", 城市 "city", 村民 "villagers"), so a
# greedy prefix reliably corrupts the estate name whenever real body text
# follows it - and since the corrupted string differs per occurrence
# (whatever word happens to follow), it also breaks the learned-corrections
# cache (app.posters.corrections): every mention of the same real estate
# gets treated as a distinct, never-before-seen key, so district never
# gets learned for it. Non-greedy stops at the first (shortest, correct)
# suffix match instead.
_ESTATE_SUFFIX_RE = re.compile(
    r"([一-鿿]{2,8}?(?:邨|苑|村|花園|花园|大廈|大厦|樓|楼|閣|阁|城|居|坊|軒|轩|灣|湾|中心))"
)

# A segment made up of nothing but estate/building names and route
# connector words ("愉翠苑來往大埔富蝶邨" = "Yue Chui Court to/from Fu Wo
# Estate") describes where a route goes, not descriptive title content -
# used by _extract_title to drop such a hyphen-delimited segment entirely
# rather than fold it into the title.
_ROUTE_DESCRIPTION_TOKEN_RE = re.compile(
    r"(?:[一-鿿]{2,10}(?:邨|苑|村|花園|花园|大廈|大厦|樓|楼|閣|阁|城|居|坊|軒|轩|灣|湾|中心)|來往|来往|往|至)"
)

# After every other cleanup, a title made of nothing but punctuation/
# whitespace (e.g. a lone "-" left over from stripping) is not a title -
# it's the parser having found nothing, and must fall through to None
# rather than store useless punctuation as if it meant something.
_PUNCTUATION_ONLY_RE = re.compile(r"^[\-–—_.,:：、，\s]*$")

_HYPHEN_SPLIT_RE = re.compile(r"[-–—_]+")


def _split_segments(text: str) -> list[str]:
    return [s.strip() for s in _HYPHEN_SPLIT_RE.split(text) if s.strip()]


@dataclass
class ParsedPoster:
    """One record extracted from a pasted block. `dropbox_url` and
    `source_text` are always populated (a block is only ever turned into a
    ParsedPoster once a Dropbox link is confirmed present) - every other
    field is best-effort and may be None.

    `field_confidence`/`field_sources` give a 0.0-1.0 confidence and a
    source tag ("regex" | "rule_engine" | "ai" | "default") per field, so
    a caller can flag exactly the fields that were low-confidence or
    AI-guessed instead of an all-or-nothing needs_review flag.

    `campaign_name` has no reliable regex/keyword heuristic (unlike
    district/estate/department, campaign names aren't drawn from a small,
    enumerable vocabulary) and is deliberately left for manual entry
    rather than guessed - see this module's docstring's "leave it blank
    instead of crashing" policy, which extends to "leave it blank instead
    of guessing wrong"."""

    dropbox_url: str
    source_text: str
    district: str | None = None
    region: str | None = None
    estate: str | None = None
    poster_title: str | None = None
    poster_type: str | None = None
    route_number: str | None = None
    politicians: list[str] = field(default_factory=list)
    document_date: datetime | None = None
    date_to: datetime | None = None
    language: str | None = None
    version: str | None = None
    government_department: str | None = None
    campaign_name: str | None = None
    keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_review: bool = False
    field_confidence: dict[str, float] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)


def _extract_date(text: str) -> datetime | None:
    match = _DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None  # e.g. "2026-13-40" - not a real date, leave blank


def _extract_date_range(text: str) -> tuple[datetime | None, datetime | None]:
    """Returns (date_from, date_to). date_to is only populated when a
    second, distinct date is found in the same text - most records name
    only one date, in which case date_to stays None (never invented)."""
    dates: list[datetime] = []
    for match in _DATE_RE.finditer(text):
        try:
            dates.append(datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            continue
    if not dates:
        return None, None
    if len(dates) == 1 or dates[0] == dates[1]:
        return dates[0], None
    return dates[0], dates[1]


def _extract_route(text: str) -> str | None:
    # Strip any recognisable date first: a hyphen/slash-separated date
    # like "2026-07-10" would otherwise leave "07"/"10" as plausible-
    # looking 2-digit route candidates that a plain digit-run-length check
    # can't distinguish from a real route, and finditer would find one of
    # those before ever reaching the text's actual route code.
    text = _DATE_RE.sub(" ", text)
    for match in _ROUTE_RE.finditer(text):
        token = match.group(1)
        if token.isdigit() and len(token) > 3:
            continue  # a bare 4+ digit run is a date/id, not a route code
        if len(token) < _MIN_ROUTE_LENGTH:
            continue  # a bare single digit is far more often a stray version/page number
        return token
    return None


def _is_route_description_segment(segment: str) -> bool:
    """True if `segment` is entirely composed of estate/building suffix
    names and route connector words ("來往"/"往"/"至") - i.e. the whole
    segment describes where a route goes, not descriptive title content."""
    tokens = _ROUTE_DESCRIPTION_TOKEN_RE.findall(segment)
    return bool(tokens) and "".join(tokens) == segment


def _is_non_title_segment(segment: str, *, type_segment: str | None = None) -> bool:
    """True if `segment` (one hyphen-delimited piece of a metadata line)
    is fully explained by another field this parser extracts elsewhere,
    and so should not be folded into the title.

    `type_segment` is the *one* segment actually chosen as the record's
    poster_type (see _extract_poster_type_from_segments) - only that exact
    segment is excluded as "the type marker" here. A different segment
    that also happens to be a dict key (e.g. "好消息" when an earlier
    segment "海報" already won the type slot) is left as fair game for the
    title instead of being blanket-excluded just for appearing in
    _POSTER_TYPE_KEYWORDS - the same word can be either a category marker
    or a record's actual descriptive subject depending on context, and
    only the segment that *won* is the former."""
    if _DATE_RE.fullmatch(segment):
        return True
    if type_segment is not None and segment == type_segment:
        return True
    if len(segment) >= _MIN_ROUTE_LENGTH and _ROUTE_RE.fullmatch(segment):
        return True
    if segment.isdigit():
        return True  # stray numeric noise (page/version fragment), never a title
    if _is_route_description_segment(segment):
        return True
    return False


def _extract_title(
    text: str, district_tokens: list[str] | None = None, *, type_segment: str | None = None
) -> tuple[str | None, float, str]:
    """Returns (title, confidence, source)."""
    match = _BRACKET_RE.search(text)
    if match:
        title = (match.group(1) or match.group(2) or "").strip()
        return (title, 1.0, "regex") if title else (None, 0.0, "none")

    stripped = " ".join(text.split())
    tokens = sorted({t for t in (district_tokens or []) + _HK_DISTRICTS_ZH if t}, key=len, reverse=True)
    for token in tokens:
        if stripped.startswith(token):
            rest = stripped[len(token):].lstrip(" \t　-–—:：、，,")
            if rest:
                stripped = rest
            break

    if not stripped or _PUNCTUATION_ONLY_RE.match(stripped):
        return None, 0.0, "none"

    segments = _split_segments(stripped)
    if len(segments) > 1:
        title_segments = [s for s in segments if not _is_non_title_segment(s, type_segment=type_segment)]
        if not title_segments:
            # Every segment was a date/type/route/route-description - there
            # is genuinely no title content here, not a parsing failure to
            # recover from by falling back to the raw line (which would
            # just reintroduce the fields we determined don't belong here).
            return None, 0.0, "none"
        candidate = " ".join(title_segments)
        if _PUNCTUATION_ONLY_RE.match(candidate):
            return None, 0.0, "none"
        return candidate, 0.85, "regex"

    return stripped, 0.5, "regex"


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


def _extract_poster_type_from_segments(segments: list[str]) -> tuple[str | None, str | None]:
    """Segment-exact-match poster type detection: only a hyphen-delimited
    segment that *exactly* equals a known type keyword counts (the first
    one found, in order) - unlike _extract_poster_type's whole-text
    substring scan, this deliberately does not match a keyword merely
    embedded within a longer descriptive segment (e.g. "工程" inside
    "...改善工程" is part of the title's subject matter, not a poster-type
    marker, and must not be misclassified as the "works" category just
    because that word appears somewhere in the title).

    Returns (poster_type, matched_segment) - the caller needs the exact
    segment text too, so _extract_title can exclude only *that* segment
    from the title rather than every segment that happens to also be a
    dict key (see _is_non_title_segment's `type_segment` param)."""
    for segment in segments:
        if segment in _POSTER_TYPE_KEYWORDS:
            return _POSTER_TYPE_KEYWORDS[segment], segment
    return None, None


def _extract_version(text: str) -> str | None:
    match = _VERSION_RE.search(text)
    if not match:
        return None
    return next(g for g in match.groups() if g is not None)


def _extract_government_department(text: str) -> str | None:
    for keyword, department in _GOV_DEPARTMENT_KEYWORDS.items():
        if keyword in text:
            return department
    return None


_HAS_MEANINGFUL_CONTENT_RE = re.compile(r"[一-鿿A-Za-z0-9]")


def _is_garbage_title(title: str | None) -> bool:
    """A title with no CJK character and no Latin letter/digit at all
    (e.g. "@@@ ### !!!") carries no real information - treated the same
    as no title for confidence purposes, even though _extract_title's
    fallback branch technically returned a non-empty string for it."""
    return title is None or not _HAS_MEANINGFUL_CONTENT_RE.search(title)


def _extract_estate_fallback(text: str) -> str | None:
    """Regex-only fallback for when RuleEngine's alias/fuzzy match (and its
    own AI fallback) can't find the estate - most commonly because the
    estate isn't in config/rules/estates.yaml yet. Picks the left-most
    (i.e. first-mentioned) CJK run ending in a common estate/building
    suffix, since posters typically name the poster's own estate before
    any destination estate mentioned later (e.g. "... 來往 ...")."""
    match = _ESTATE_SUFFIX_RE.search(text)
    if match:
        return match.group(1)
    return None


def _extract_keywords(text: str, already_extracted: list[str]) -> list[str]:
    keywords: list[str] = []
    for needle, canonical in _TOPIC_KEYWORDS.items():
        if needle in text and canonical not in keywords:
            keywords.append(canonical)

    remainder = _BRACKET_RE.sub(" ", text)
    for token in already_extracted:
        remainder = remainder.replace(token, " ")
    parts = re.split(r"[\-–—_/,，、\s]+", remainder)
    for part in parts:
        cleaned = part.strip("【】「」[]()（）")
        if (
            cleaned
            and cleaned not in _STOPWORDS
            and cleaned not in keywords
            and len(cleaned) > 1
            and not cleaned.isdigit()
        ):
            keywords.append(cleaned)
    return keywords[:12]


def _normalize_line(line: str) -> str:
    """Strips ordinary whitespace plus invisible unicode characters (zero-
    width space, BOM, etc.) that commonly survive copy-paste from web
    pages/rich text editors. Without this, a separator line that *looks*
    blank but carries one of these characters is non-empty to plain
    str.strip(), so it gets treated as real content instead of a blank
    line - the underlying cause of blocks silently merging two or more
    records together and losing the metadata <-> URL association."""
    return _INVISIBLE_RE.sub("", line).strip()


def split_into_blocks(raw_text: str) -> list[str]:
    """Walks the pasted text pairing each Dropbox link with the single
    closest preceding non-empty line ("Line 1: metadata, Line 2: Dropbox
    URL, repeat"), rather than accumulating everything since the last
    completed record. This is deliberately robust to inconsistent spacing,
    extra blank lines, and invisible/whitespace-only separator lines: any
    number of blank lines may sit between the metadata line and its URL,
    and stray text further back is never pulled in - only the nearest
    preceding line is used. A URL with no preceding line at all (or only
    blank ones) yields a block with just the URL, which parse_block will
    later fall back to "(untitled)" for since there is truly nothing else
    to extract a title from. Text with no Dropbox link anywhere returns no
    blocks - there is nothing importable in it, a normal, non-error case."""
    if not raw_text or not raw_text.strip():
        return []

    blocks: list[str] = []
    pending_meta: str | None = None
    for raw_line in raw_text.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue  # blank (or invisible-only) separator - keep waiting
        if DROPBOX_URL_RE.search(line):
            blocks.append(f"{pending_meta}\n{line}" if pending_meta else line)
            pending_meta = None
        else:
            pending_meta = line  # closest-preceding-line wins, not accumulate
    return blocks


def parse_block(
    block: str,
    rule_engine: RuleEngine | None,
    *,
    estate_service: EstateMetadataService | None = None,
    db: Session | None = None,
) -> ParsedPoster | None:
    """Parses one block into a ParsedPoster, or None if it has no Dropbox
    link (nothing to import). Every other field is extracted independently
    and defensively - one field's extractor raising never prevents the
    others from populating.

    `estate_service` defaults to wrapping `rule_engine` when omitted (the
    common case - callers only need to pass a distinct instance if they
    want to override estate-metadata resolution independently of district/
    estate name resolution). `db` enables the AI fallback's result cache
    (app.posters.ai_fallback) - omitted (None), the AI fallback is simply
    skipped, matching every other "AI is optional" path in this app.
    """
    url_match = DROPBOX_URL_RE.search(block)
    if url_match is None:
        return None

    dropbox_url = url_match.group(0).rstrip(").,;、")
    text_only = " ".join(DROPBOX_URL_RE.sub(" ", block).split())

    parsed = ParsedPoster(dropbox_url=dropbox_url, source_text=block.strip())

    if estate_service is None and rule_engine is not None:
        estate_service = EstateMetadataService(rule_engine)

    try:
        parsed.document_date, parsed.date_to = _extract_date_range(text_only)
    except Exception:
        parsed.warnings.append("date_extraction_failed")
    parsed.field_confidence["document_date"] = 1.0 if parsed.document_date else 0.0
    parsed.field_sources["document_date"] = "regex" if parsed.document_date else "none"

    try:
        parsed.route_number = _extract_route(text_only)
    except Exception:
        parsed.warnings.append("route_extraction_failed")
    parsed.field_confidence["route_number"] = 1.0 if parsed.route_number else 0.0
    parsed.field_sources["route_number"] = "regex" if parsed.route_number else "none"

    segments = _split_segments(text_only)
    type_segment: str | None = None
    try:
        if len(segments) > 1:
            parsed.poster_type, type_segment = _extract_poster_type_from_segments(segments)
        else:
            parsed.poster_type = _extract_poster_type(text_only)
    except Exception:
        parsed.warnings.append("poster_type_extraction_failed")

    try:
        parsed.language = _detect_language(text_only)
    except Exception:
        parsed.warnings.append("language_detection_failed")

    resolved_district_tokens: list[str] = []
    district_confidence: float | None = None
    estate_confidence: float | None = None

    # Estate resolution runs *before* an independent whole-text district
    # scan, and - once an estate resolves - its own district/region comes
    # from that estate's metadata bundle, not a second, separate text scan.
    # Without this ordering, a record naming both its own estate and a
    # route's destination estate in another district (e.g. "愉翠苑來往大埔
    # 富蝶邨" - Sha Tin's Yue Chui Court, "to/from" Tai Po's Fu Wo Estate)
    # would have its *district* hijacked by whichever district name the
    # whole-text scan happens to score higher, even though the record's own
    # district is unambiguous once you know which estate it's actually
    # about.
    if estate_service is not None:
        try:
            meta = estate_service.resolve(text_only)
            if meta is not None:
                parsed.estate = meta.estate_name
                estate_confidence = meta.confidence
                parsed.district = meta.district_name
                parsed.region = meta.region
                if meta.politicians:
                    parsed.politicians = meta.politicians
        except Exception:
            parsed.warnings.append("estate_resolution_failed")

    if rule_engine is not None and parsed.district is None:
        try:
            district = rule_engine.resolve_district(text_only)
            if district is not None:
                parsed.district = district.native_name
                parsed.region = district.region
                resolved_district_tokens = [district.name, district.id, district.native_name, *district.aliases]
                district_confidence = rule_engine.last_district_confidence
        except Exception:
            parsed.warnings.append("district_resolution_failed")

    if parsed.estate is None:
        try:
            parsed.estate = _extract_estate_fallback(text_only)
        except Exception:
            parsed.warnings.append("estate_extraction_failed")

    learned_district = False
    ai_district = False
    if parsed.district is None and parsed.estate is not None and db is not None:
        # The estate resolved (via config/rules/estates.yaml or the regex
        # suffix fallback) but isn't in the curated YAML, so nothing knows
        # its district yet - check whether staff have already corrected
        # this exact estate name on a past record (app.posters.corrections)
        # before giving up. This is what makes the parser improve over
        # time without a YAML edit + redeploy for every unlisted estate.
        try:
            from app.posters.corrections import lookup_correction, record_correction

            learned = lookup_correction(db, key_type="estate_name", key_value=parsed.estate, field="district")
            if learned:
                parsed.district = learned
                learned_district = True
            elif rule_engine is not None:
                # Layer 3: neither the YAML nor a staff correction knows
                # this estate - ask the AI provider which district it's in
                # (a narrow, well-cached question, not the whole-record
                # extraction below). The answer is immediately persisted
                # as a learned correction too, so this estate never needs
                # asking again regardless of whether AI stays configured.
                from app.posters.ai_fallback import ai_infer_district_for_estate

                district_names = [d.native_name for d in rule_engine.ruleset.districts]
                ai_answer = ai_infer_district_for_estate(db, parsed.estate, district_names)
                if ai_answer:
                    parsed.district = ai_answer
                    ai_district = True
                    record_correction(
                        db, key_type="estate_name", key_value=parsed.estate, field="district",
                        value=ai_answer, corrected_by=None,
                    )
        except Exception:
            parsed.warnings.append("learned_correction_lookup_failed")

    # `district` may have come directly from a district-text match
    # (district_confidence), from the estate that resolved first
    # (estate_confidence), from a staff-taught correction
    # (learned_district), or from the AI fallback (ai_district) - all four
    # are real, confident-enough resolutions, not "not found". A learned
    # correction is staff-verified ground truth (full confidence); an AI
    # answer is a reasonable guess, reported at the same moderate
    # confidence RuleEngine already uses for its own AI-assisted matches.
    if learned_district:
        district_confidence = 1.0
    elif ai_district:
        district_confidence = 0.6
    effective_district_confidence = district_confidence if district_confidence is not None else estate_confidence
    parsed.field_confidence["district"] = effective_district_confidence if effective_district_confidence else 0.0
    parsed.field_sources["district"] = (
        "learned" if learned_district else ("ai" if ai_district else ("rule_engine" if effective_district_confidence else "none"))
    )
    parsed.field_confidence["estate"] = estate_confidence if estate_confidence else (0.6 if parsed.estate else 0.0)
    parsed.field_sources["estate"] = "rule_engine" if estate_confidence else ("regex" if parsed.estate else "none")

    try:
        parsed.poster_title, title_confidence, title_source = _extract_title(
            text_only, resolved_district_tokens, type_segment=type_segment
        )
    except Exception:
        parsed.warnings.append("title_extraction_failed")
        title_confidence, title_source = 0.0, "none"
    parsed.field_confidence["poster_title"] = title_confidence
    parsed.field_sources["poster_title"] = title_source

    # Poster type default: a record with a resolved date and a genuine
    # (non-garbage) title, but no explicit type keyword anywhere in the
    # text, is still almost always some kind of notice/circular rather
    # than an un-classifiable record - defaulting to "notice" here (at a
    # deliberately lower confidence than an actual keyword match) avoids
    # leaving an obviously-a-notice record's type blank purely because it
    # didn't happen to use one of the recognised keywords.
    if parsed.poster_type is not None:
        parsed.field_confidence["poster_type"] = 1.0
        parsed.field_sources["poster_type"] = "regex"
    elif parsed.document_date is not None and not _is_garbage_title(parsed.poster_title):
        parsed.poster_type = "notice"
        parsed.field_confidence["poster_type"] = 0.4
        parsed.field_sources["poster_type"] = "default"
    else:
        parsed.field_confidence["poster_type"] = 0.0
        parsed.field_sources["poster_type"] = "none"

    try:
        parsed.version = _extract_version(text_only)
    except Exception:
        parsed.warnings.append("version_extraction_failed")

    try:
        parsed.government_department = _extract_government_department(text_only)
    except Exception:
        parsed.warnings.append("government_department_extraction_failed")

    try:
        already = [v for v in (parsed.district, parsed.estate, parsed.route_number) if v]
        parsed.keywords = _extract_keywords(text_only, already)
    except Exception:
        parsed.warnings.append("keyword_extraction_failed")

    # Confidence check: if none of the record's three most identifying
    # fields resolved with any confidence, there's a real chance the
    # metadata line didn't match the expected shape at all (garbled paste,
    # an unsupported format, noise). Rather than silently inserting a
    # record that's effectively "district: none, estate: none, title:
    # noise", try the AI fallback (if a db session was given and an AI
    # provider is available/allowed) before giving up and flagging it for
    # manual review - per the requirement to never insert low-confidence
    # data as if it were reliable, but also to never ask a human unless
    # both the rule-based parser and the AI fallback have failed.
    if parsed.district is None and parsed.estate is None and _is_garbage_title(parsed.poster_title):
        if db is not None:
            _apply_ai_fallback(parsed, db, block)
        if parsed.district is None and parsed.estate is None and _is_garbage_title(parsed.poster_title):
            parsed.needs_review = True

    return parsed


def _apply_ai_fallback(parsed: ParsedPoster, db: Session, block: str) -> None:
    """Fills in title/district/estate/poster_type from the AI fallback
    (app.posters.ai_fallback) wherever the rule-based pass left them
    unresolved - never overwrites a field the rule-based pass already
    populated, and never raises (a failed/unavailable AI call simply
    leaves the record as the rule-based pass left it)."""
    from app.posters.ai_fallback import get_ai_extracted_fields

    try:
        result = get_ai_extracted_fields(db, block)
    except Exception:
        parsed.warnings.append("ai_fallback_failed")
        return
    if not result:
        return

    if _is_garbage_title(parsed.poster_title) and result.get("title"):
        parsed.poster_title = str(result["title"])
        parsed.field_confidence["poster_title"] = 0.6
        parsed.field_sources["poster_title"] = "ai"
    if parsed.district is None and result.get("district"):
        parsed.district = str(result["district"])
        parsed.field_confidence["district"] = 0.6
        parsed.field_sources["district"] = "ai"
    if parsed.estate is None and result.get("estate"):
        parsed.estate = str(result["estate"])
        parsed.field_confidence["estate"] = 0.6
        parsed.field_sources["estate"] = "ai"
    if parsed.poster_type is None and result.get("poster_type"):
        parsed.poster_type = str(result["poster_type"])
        parsed.field_confidence["poster_type"] = 0.6
        parsed.field_sources["poster_type"] = "ai"


def parse_poster_text(
    raw_text: str,
    rule_engine: RuleEngine | None = None,
    *,
    estate_service: EstateMetadataService | None = None,
    db: Session | None = None,
) -> list[ParsedPoster]:
    """Top-level entry point used by POST /api/posters/import. Splits a
    large pasted blob into records and parses each - never raises for
    malformed/inconsistent input; a block with no Dropbox link is silently
    skipped, and every field within a parsed block degrades independently.
    """
    return [
        parsed
        for block in split_into_blocks(raw_text)
        if (parsed := parse_block(block, rule_engine, estate_service=estate_service, db=db)) is not None
    ]
