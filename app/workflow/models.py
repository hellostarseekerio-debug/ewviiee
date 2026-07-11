"""Data structures for workflow definitions and execution context."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


STAGE_ORDER = [
    "import",
    "classify",
    "ocr",
    "extract",
    "validate",
    "apply_rules",
    "generate",
    "review",
    "export",
    "archive",
    "log",
]


@dataclass
class WorkflowDefinition:
    """Parsed from a YAML file under config/workflows/. Each stage maps to a
    plugin-provided handler name; stages can be disabled/reordered/extended
    purely through configuration."""

    name: str
    display_name: str
    plugin: str
    stages: list[str] = field(default_factory=lambda: list(STAGE_ORDER))
    stage_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    description: str = ""


@dataclass
class StageResult:
    stage: str
    success: bool
    detail: str = ""
    duration_ms: int = 0
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    """Mutable state threaded through every stage of a single document's run."""

    document_path: Path
    workflow: WorkflowDefinition
    document_id: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    ai_confidence: float | None = None
    validation_errors: list[str] = field(default_factory=list)
    output_path: Path | None = None
    archive_path: Path | None = None
    stage_results: list[StageResult] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""
