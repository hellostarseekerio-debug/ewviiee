"""AI provider abstraction.

Every provider implements this Protocol. The rest of the application only
ever depends on `AIProvider`, never on a concrete SDK, so switching between
OpenAI / Anthropic / Azure OpenAI / a local LLM is a configuration change
(`OAP_AI_PROVIDER`), not a code change.

AI is used only as a fallback when deterministic rule-engine matching fails
(e.g. an estate name OCR'd with noise that no alias in rules/estates.yaml
covers). Callers should always attempt rule-based resolution first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class AIResponse:
    text: str
    confidence: float | None = None
    raw: dict = field(default_factory=dict)


@runtime_checkable
class AIProvider(Protocol):
    name: str

    def classify(self, text: str, categories: list[str], context: str = "") -> AIResponse:
        """Classify `text` into one of `categories`."""
        ...

    def extract_fields(self, text: str, schema: dict[str, str], context: str = "") -> AIResponse:
        """Extract structured fields described by `schema` (field -> description)."""
        ...

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        """General purpose completion, used for anything not covered above."""
        ...
