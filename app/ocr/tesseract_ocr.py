"""Tesseract backend - fallback OCR engine used when PaddleOCR confidence is low
or PaddleOCR itself is unavailable/fails."""
from __future__ import annotations

from pathlib import Path

from app.ocr.base import OCRResult, OCRWord

_LANG_MAP = {
    "ch_tra": "chi_tra",
    "ch_sim": "chi_sim",
    "en": "eng",
}


class TesseractOCRBackend:
    name = "tesseract"

    def run(self, image_path: Path, languages: list[str]) -> OCRResult:
        import pytesseract
        from PIL import Image

        tess_langs = "+".join(_LANG_MAP.get(lang, lang) for lang in languages)
        image = Image.open(image_path)
        data = pytesseract.image_to_data(
            image, lang=tess_langs, output_type=pytesseract.Output.DICT
        )

        words: list[OCRWord] = []
        lines: list[str] = []
        confidences: list[float] = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text:
                continue
            conf_raw = data["conf"][i]
            confidence = max(float(conf_raw), 0.0) / 100.0
            lines.append(text)
            confidences.append(confidence)
            words.append(
                OCRWord(
                    text=text,
                    confidence=confidence,
                    bbox=(
                        data["left"][i],
                        data["top"][i],
                        data["left"][i] + data["width"][i],
                        data["top"][i] + data["height"][i],
                    ),
                )
            )
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return OCRResult(
            text=" ".join(lines), confidence=avg_conf, words=words, engine=self.name,
            language=",".join(languages),
        )
