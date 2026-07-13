"""Loads and evaluates the YAML-driven rule set.

Responsible for:
- Loading districts/estates/aliases/mappings/validation/naming rules from YAML.
- Resolving noisy OCR'd text to a canonical district/estate via alias matching.
- Falling back to the AI provider only when no rule/alias matches, per the
  platform's "deterministic first" policy.
- Validating extracted document fields against configured ValidationRule list.
- Building output filenames/paths from the configured naming rule.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml

from app.ai.base import AIProvider
from app.core.logging_config import get_logger
from app.rules.fuzzy import best_match
from app.rules.schema import District, Estate, NamingRule, RuleSet, ValidationRule

logger = get_logger("rules.engine")


def load_ruleset(config_dir: Path) -> RuleSet:
    rules_dir = config_dir / "rules"
    ruleset = RuleSet()

    districts_file = rules_dir / "districts.yaml"
    if districts_file.exists():
        data = yaml.safe_load(districts_file.read_text(encoding="utf-8")) or {}
        ruleset.districts = [
            District(
                id=d["id"],
                name=d["name"],
                aliases=d.get("aliases", []),
                region=d.get("region"),
            )
            for d in data.get("districts", [])
        ]

    estates_file = rules_dir / "estates.yaml"
    if estates_file.exists():
        data = yaml.safe_load(estates_file.read_text(encoding="utf-8")) or {}
        ruleset.estates = [
            Estate(
                id=e["id"],
                name=e["name"],
                district_id=e["district_id"],
                aliases=e.get("aliases", []),
                common_routes=e.get("common_routes", []),
                politicians=e.get("politicians", []),
                dropbox_folder=e.get("dropbox_folder"),
                poster_templates=e.get("poster_templates", []),
            )
            for e in data.get("estates", [])
        ]

    aliases_file = rules_dir / "aliases.yaml"
    if aliases_file.exists():
        data = yaml.safe_load(aliases_file.read_text(encoding="utf-8")) or {}
        ruleset.aliases = data.get("aliases", {})

    validation_file = rules_dir / "validation.yaml"
    if validation_file.exists():
        data = yaml.safe_load(validation_file.read_text(encoding="utf-8")) or {}
        ruleset.validation_rules = [ValidationRule(**rule) for rule in data.get("rules", [])]
        ruleset.date_rules = data.get("date_rules", {})

    naming_file = rules_dir / "naming.yaml"
    if naming_file.exists():
        data = yaml.safe_load(naming_file.read_text(encoding="utf-8")) or {}
        if "pattern" in data:
            ruleset.naming_rule = NamingRule(
                pattern=data["pattern"], date_format=data.get("date_format", "%Y%m%d")
            )
        ruleset.output_folders = data.get("output_folders", {})

    mappings_file = rules_dir / "poster_mappings.yaml"
    if mappings_file.exists():
        data = yaml.safe_load(mappings_file.read_text(encoding="utf-8")) or {}
        ruleset.page_mappings = data.get("page_mappings", {})
        ruleset.poster_mappings = data.get("poster_mappings", {})

    return ruleset


class RuleEngine:
    def __init__(self, ruleset: RuleSet, ai_provider: AIProvider | None = None) -> None:
        self.ruleset = ruleset
        self._ai_provider = ai_provider
        # Confidence of the most recent resolve_district/resolve_estate call
        # (1.0 = exact/alias match, <1.0 = fuzzy match, None = resolved via
        # AI or unresolved). Plugins read this to report an honest
        # confidence score instead of a hardcoded constant.
        self.last_district_confidence: float | None = None
        self.last_estate_confidence: float | None = None

    # ---- Resolution --------------------------------------------------------

    def resolve_district(self, text: str) -> District | None:
        candidates = [
            (district, [district.name, district.id, *district.aliases])
            for district in self.ruleset.districts
        ]
        match = best_match(text, candidates)
        if match is not None:
            self.last_district_confidence = match.confidence
            return match.entry
        self.last_district_confidence = None
        return self._resolve_via_ai_district(text)

    def resolve_estate(self, text: str, district_id: str | None = None) -> Estate | None:
        pool = self.ruleset.estates
        if district_id:
            pool = [e for e in pool if e.district_id == district_id]
        candidates = [(estate, [estate.name, estate.id, *estate.aliases]) for estate in pool]
        match = best_match(text, candidates)
        if match is not None:
            self.last_estate_confidence = match.confidence
            return match.entry
        self.last_estate_confidence = None
        return self._resolve_via_ai_estate(text, pool)

    def _resolve_via_ai_district(self, text: str) -> District | None:
        if not self._ai_provider or not self.ruleset.districts:
            return None
        logger.info("rule_engine_ai_fallback", field="district")
        names = [d.name for d in self.ruleset.districts]
        try:
            response = self._ai_provider.classify(
                text, names, context="Identify the Hong Kong district."
            )
        except Exception as exc:
            # AI is a best-effort fallback, never a hard dependency - a
            # network hiccup or provider outage must not crash the pipeline.
            logger.warning("ai_fallback_failed", field="district", error=str(exc))
            return None
        for district in self.ruleset.districts:
            if _normalize(district.name) == _normalize(response.text):
                # AI resolution is reported at a fixed, moderate confidence -
                # it is a fallback of last resort and should never be
                # mistaken for a confirmed exact/fuzzy rule match downstream.
                self.last_district_confidence = 0.6
                return district
        return None

    def _resolve_via_ai_estate(self, text: str, pool: list[Estate]) -> Estate | None:
        if not self._ai_provider or not pool:
            return None
        logger.info("rule_engine_ai_fallback", field="estate")
        names = [e.name for e in pool]
        try:
            response = self._ai_provider.classify(
                text, names, context="Identify the housing estate name."
            )
        except Exception as exc:
            logger.warning("ai_fallback_failed", field="estate", error=str(exc))
            return None
        for estate in pool:
            if _normalize(estate.name) == _normalize(response.text):
                self.last_estate_confidence = 0.6
                return estate
        return None

    def resolve_alias(self, text: str) -> str:
        normalized = _normalize(text)
        return self.ruleset.aliases.get(normalized, text)

    # ---- Validation ---------------------------------------------------------

    def validate_fields(self, fields: dict[str, object]) -> list[str]:
        errors: list[str] = []
        for rule in self.ruleset.validation_rules:
            value = fields.get(rule.field)
            if rule.required and (value is None or value == ""):
                errors.append(f"Missing required field: {rule.field}")
                continue
            if value is None:
                continue
            str_value = str(value)
            if rule.pattern and not re.match(rule.pattern, str_value):
                errors.append(f"Field '{rule.field}' value '{str_value}' does not match pattern")
            if rule.min_length and len(str_value) < rule.min_length:
                errors.append(f"Field '{rule.field}' shorter than {rule.min_length} chars")
            if rule.max_length and len(str_value) > rule.max_length:
                errors.append(f"Field '{rule.field}' longer than {rule.max_length} chars")
        return errors

    # ---- Naming ---------------------------------------------------------------

    def build_output_name(self, fields: dict[str, object], extension: str = ".pdf") -> str:
        if not self.ruleset.naming_rule:
            raise ValueError("No naming rule configured")
        pattern = self.ruleset.naming_rule.pattern
        context = dict(fields)
        if "date" in context and isinstance(context["date"], datetime):
            context["date"] = context["date"].strftime(self.ruleset.naming_rule.date_format)
        name = pattern.format(**context)
        return f"{name}{extension}"

    def output_folder_for(self, category: str) -> str:
        return self.ruleset.output_folders.get(category, category)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()
