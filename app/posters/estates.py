"""EstateMetadataService: a typed, resolution-oriented view over the
YAML-driven district/estate data (config/rules/districts.yaml,
config/rules/estates.yaml) that the new metadata extraction pipeline
(app/posters/parser.py) uses to auto-fill District/Region/Politicians/
Dropbox-folder/Poster-templates the moment an estate is recognised -
rather than leaving those to a second, separate lookup a human has to do
by hand.

Deliberately a thin service over app.rules.engine.RuleEngine, not a
parallel data store: RuleEngine already owns loading, alias/fuzzy
matching, and (for districts/estates specifically) AI-assisted
resolution when nothing else matches. This module only adds the
"resolve once, return everything associated with the result" convenience
and a typed `EstateMetadata` result shape for callers that don't want to
reach into RuleEngine/Estate/District directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rules.engine import RuleEngine
from app.rules.schema import District, Estate


@dataclass
class EstateMetadata:
    estate_id: str
    estate_name: str
    district_id: str
    district_name: str
    region: str | None
    common_routes: list[str]
    politicians: list[str]
    dropbox_folder: str | None
    poster_templates: list[str]
    confidence: float | None  # RuleEngine.last_estate_confidence at resolution time


class EstateMetadataService:
    """Wraps a RuleEngine to answer "given this estate (or this raw text),
    what else do we already know?" in one call."""

    def __init__(self, rule_engine: RuleEngine) -> None:
        self._rule_engine = rule_engine

    def _district_for(self, district_id: str) -> District | None:
        return next((d for d in self._rule_engine.ruleset.districts if d.id == district_id), None)

    def _to_metadata(self, estate: Estate) -> EstateMetadata:
        district = self._district_for(estate.district_id)
        return EstateMetadata(
            estate_id=estate.id,
            estate_name=estate.native_name,
            district_id=estate.district_id,
            district_name=district.native_name if district else estate.district_id,
            region=district.region if district else None,
            common_routes=list(estate.common_routes),
            politicians=list(estate.politicians),
            dropbox_folder=estate.dropbox_folder,
            poster_templates=list(estate.poster_templates),
            confidence=self._rule_engine.last_estate_confidence,
        )

    def resolve(self, text: str, *, district_id: str | None = None) -> EstateMetadata | None:
        """Resolves `text` to an estate (via RuleEngine's alias/fuzzy/AI
        resolution) and returns its full metadata bundle, or None if no
        estate could be resolved at all."""
        estate = self._rule_engine.resolve_estate(text, district_id=district_id)
        if estate is None:
            return None
        return self._to_metadata(estate)

    def region_for_district(self, district_id: str) -> str | None:
        district = self._district_for(district_id)
        return district.region if district else None

    def native_district_name(self, district_id: str) -> str | None:
        district = self._district_for(district_id)
        return district.native_name if district else None
