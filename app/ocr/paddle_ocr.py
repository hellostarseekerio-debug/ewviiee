"""PaddleOCR backend - primary OCR engine, best accuracy for Chinese/mixed text."""
from __future__ import annotations

from pathlib import Path

from app.ocr.base import OCRResult, OCRWord

_LANG_MAP = {
    "ch_tra": "chinese_cht",
    "ch_sim": "ch",
    "en": "en",
}


class PaddleOCRBackend:
    name = "paddle"

    def __init__(self) -> None:
        self._engines: dict[str, object] = {}

    def _get_engine(self, lang: str):
        if lang not in self._engines:
            from paddleocr import PaddleOCR  # optional heavy dependency

            self._engines[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        return self._engines[lang]

    def run(self, image_path: Path, languages: list[str]) -> OCRResult:
        best: OCRResult | None = None
        for lang in languages:
            paddle_lang = _LANG_MAP.get(lang, lang)
            engine = self._get_engine(paddle_lang)
            raw_result = engine.ocr(str(image_path), cls=True)
            words: list[OCRWord] = []
            lines: list[str] = []
            confidences: list[float] = []
            for page in raw_result or []:
                for box, (text, confidence) in page:
                    lines.append(text)
                    confidences.append(confidence)
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    words.append(
                        OCRWord(
                            text=text,
                            confidence=confidence,
                            bbox=(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
                        )
                    )
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            candidate = OCRResult(
                text="\n".join(lines), confidence=avg_conf, words=words, engine=self.name, language=lang
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate
        return best or OCRResult(text="", confidence=0.0, engine=self.name)
