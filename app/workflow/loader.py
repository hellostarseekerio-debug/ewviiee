"""Loads WorkflowDefinition objects from config/workflows/*.yaml.

Adding a brand-new workflow (e.g. "Banner Applications") only requires
dropping a new YAML file here plus a plugin implementing StageHandlerProvider
- no changes to app/workflow/engine.py itself.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.workflow.models import STAGE_ORDER, WorkflowDefinition


def load_workflow_definition(path: Path) -> WorkflowDefinition:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return WorkflowDefinition(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        plugin=data["plugin"],
        stages=data.get("stages", list(STAGE_ORDER)),
        stage_config=data.get("stage_config", {}),
        description=data.get("description", ""),
    )


def load_all_workflow_definitions(workflows_dir: Path) -> dict[str, WorkflowDefinition]:
    definitions: dict[str, WorkflowDefinition] = {}
    if not workflows_dir.exists():
        return definitions
    for yaml_path in sorted(workflows_dir.glob("*.yaml")):
        definition = load_workflow_definition(yaml_path)
        definitions[definition.name] = definition
    return definitions
