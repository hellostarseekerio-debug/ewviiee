from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.workflow.runner import _json_safe


def test_json_safe_converts_datetime():
    result = _json_safe({"date": datetime(2026, 7, 11, 10, 0, 0)})
    assert result["date"] == "2026-07-11T10:00:00"


def test_json_safe_converts_nested_path_and_datetime():
    result = _json_safe(
        {"nested": {"path": Path("/tmp/foo.pdf"), "when": datetime(2026, 1, 1)}, "items": [Path("a"), 1, "b"]}
    )
    assert result["nested"]["path"] == "/tmp/foo.pdf"
    assert result["nested"]["when"] == "2026-01-01T00:00:00"
    assert result["items"] == ["a", 1, "b"]


def test_json_safe_leaves_plain_values_untouched():
    result = _json_safe({"a": 1, "b": "text", "c": None, "d": True})
    assert result == {"a": 1, "b": "text", "c": None, "d": True}
