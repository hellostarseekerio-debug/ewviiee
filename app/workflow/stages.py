"""Stage handler protocol.

A plugin supplies a callable for any/all of the 11 pipeline stages. If a
plugin omits a stage, the workflow engine treats it as a no-op pass-through
so workflows can be lean (e.g. a simple mail-merge workflow might skip OCR).
"""
from __future__ import annotations

from typing import Callable, Protocol

from app.workflow.models import WorkflowContext

StageHandler = Callable[[WorkflowContext], None]


class StageHandlerProvider(Protocol):
    """Implemented by each workflow plugin. Returns a dict of stage name ->
    handler function; missing stages are skipped."""

    def get_stage_handlers(self) -> dict[str, StageHandler]:
        ...
