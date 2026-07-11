"""Fuzzy string matching used as a middle tier between exact/alias matching
and the AI fallback in the rule engine.

Why this exists: plain substring matching (`"tin" in "sha tin"`) is
order-dependent (whichever candidate is checked first wins, regardless of
which is the *better* match) and prone to false positives on short,
overlapping names - "Lam Tin Estate" and "Sha Tin" both contain "Tin", so a
naive substring check can resolve the wrong district. This module scores
every candidate and returns the single best match (if any) above a
confidence threshold, so:
  1. matching is order-independent (best score wins, not first hit), and
  2. a confidence score is available to feed into `ai_confidence` /
     validation reporting, and
  3. AI is only invoked when fuzzy matching is genuinely inconclusive,
     keeping the "deterministic first" policy intact while being much more
     forgiving of OCR noise/typos than exact substring matching alone.

No new dependency: built on the standard library's `difflib`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Generic, TypeVar

T = TypeVar("T")

# Below this score, a fuzzy match is not trusted - falls through to AI (if
# configured) or is treated as unresolved.
DEFAULT_THRESHOLD = 0.72

# Candidates shorter than this (e.g. 2-3 letter Latin abbreviations like
# "ST", "KT", "TM") are too short for a raw substring check to be safe -
# "ST" trivially appears inside common English words like "estate". Below
# this length, a Latin-script candidate is only trusted if it occurs at a
# whole-word boundary in the original (whitespace-preserved) text.
#
# This restriction deliberately does NOT apply to CJK candidates: Chinese
# characters carry far more information per character than Latin letters,
# CJK text has no spaces to form "words" from at all (so a word-boundary
# regex can't work), and even a 2-character CJK district name like "觀塘"
# is specific enough that substring containment is a safe, meaningful
# match rather than a coincidence.
MIN_LENGTH_FOR_SUBSTRING_MATCH = 4

_CJK_RANGE = re.compile(r"[一-鿿㐀-䶿]")


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RANGE.search(text or ""))


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _is_whole_word_match(candidate: str, text: str) -> bool:
    if not candidate:
        return False
    pattern = r"(?<!\w)" + re.escape(candidate) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _partial_ratio(candidate_n: str, text_n: str) -> float:
    """"Partial ratio": aligns `candidate_n` against the region of `text_n`
    difflib's own matcher already identifies as best-aligned, and checks
    the ratio there - instead of brute-force sliding a same-length window
    over every position in `text_n` (O(len(text_n)) SequenceMatcher calls).
    `get_matching_blocks()` is computed once in roughly linear time by
    difflib's Ratcliff-Obershelp algorithm, so this refinement is O(1)
    SequenceMatcher constructions instead of O(len(text_n)) - the
    difference that keeps `similarity()` fast against hundreds of
    candidates instead of degrading per candidate."""
    window = len(candidate_n)
    matcher = SequenceMatcher(None, text_n, candidate_n)
    best = matcher.ratio()
    for block in matcher.get_matching_blocks():
        if block.size == 0:
            continue
        start = block.a - block.b  # align candidate's start under this matched run
        start = max(0, min(start, len(text_n) - window))
        chunk = text_n[start : start + window]
        ratio = SequenceMatcher(None, candidate_n, chunk).ratio()
        if ratio > best:
            best = ratio
    return best


def similarity(candidate: str, text: str) -> float:
    """Best similarity between `candidate` and the best-aligned region of
    `text` (plus a whole-string comparison), so a short candidate name
    embedded in a longer OCR'd text block still scores highly. Returns 1.0
    for an exact match - a substring match for longer candidates, or a
    whole-word-boundary match for short ones (to avoid e.g. the alias "ST"
    trivially matching inside "estate")."""
    candidate_n = normalize(candidate)
    text_n = normalize(text)
    if not candidate_n or not text_n:
        return 0.0

    if len(candidate_n) >= MIN_LENGTH_FOR_SUBSTRING_MATCH or contains_cjk(candidate_n):
        if candidate_n in text_n or text_n in candidate_n:
            return 1.0
    elif _is_whole_word_match(candidate.strip(), text):
        return 1.0

    # The refinement below is only meaningful for candidates long enough
    # that a high ratio reflects genuine similarity rather than
    # short-string coincidence (a 2-3 char candidate can easily hit a
    # perfect or near-perfect ratio against an arbitrary same-length
    # window of unrelated text).
    can_refine = len(candidate_n) >= MIN_LENGTH_FOR_SUBSTRING_MATCH or contains_cjk(candidate_n)
    if can_refine and len(text_n) > len(candidate_n):
        return _partial_ratio(candidate_n, text_n)
    return SequenceMatcher(None, candidate_n, text_n).ratio()


@dataclass
class FuzzyMatch(Generic[T]):
    entry: T
    confidence: float


def best_match(
    text: str, candidates: list[tuple[T, list[str]]], threshold: float = DEFAULT_THRESHOLD
) -> FuzzyMatch[T] | None:
    """`candidates` is a list of (entry, [name/id/alias, ...]) pairs. Scores
    every candidate string for every entry and returns the entry with the
    single highest score, provided it clears `threshold` - or None."""
    best_entry: T | None = None
    best_score = 0.0
    for entry, names in candidates:
        for name in names:
            score = similarity(name, text)
            if score > best_score:
                best_score = score
                best_entry = entry
    if best_entry is not None and best_score >= threshold:
        return FuzzyMatch(entry=best_entry, confidence=best_score)
    return None
