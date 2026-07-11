"""OCR engine abstraction shared by PaddleOCR and Tesseract backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class OCRWord:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


@dataclass
class OCRResult:
    text: str
    confidence: float
    words: list[OCRWord] = field(default_factory=list)
    engine: str = ""
    language: str | None = None


class OCRBackend(Protocol):
    name: str

    def run(self, image_path: Path, languages: list[str]) -> OCRResult:
        ...
