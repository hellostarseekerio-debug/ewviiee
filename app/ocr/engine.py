"""OCR orchestration: primary engine + automatic fallback + confidence-based retry.

Flow:
1. Run the primary engine (PaddleOCR by default).
2. If confidence < threshold, retry with basic image pre-processing
   (upscaling / contrast) up to `ocr_max_retries` times.
3. If still below threshold, fall back to the secondary engine (Tesseract).
4. Return whichever result has the highest confidence, always reporting the
   engine and confidence used so downstream stages/logging can flag it.
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import OCREngineName, get_settings
from app.core.logging_config import get_logger
from app.ocr.base import OCRBackend, OCRResult

logger = get_logger("ocr.engine")


class OCREngine:
    def __init__(self, primary: OCRBackend | None = None, fallback: OCRBackend | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._primary = primary or self._build_backend(settings.ocr_primary_engine)
        self._fallback = fallback or self._build_backend(settings.ocr_fallback_engine)

    @staticmethod
    def _build_backend(name: OCREngineName) -> OCRBackend:
        if name == OCREngineName.PADDLE:
            from app.ocr.paddle_ocr import PaddleOCRBackend

            return PaddleOCRBackend()
        from app.ocr.tesseract_ocr import TesseractOCRBackend

        return TesseractOCRBackend()

    def _preprocess_retry(self, image_path: Path, attempt: int) -> Path:
        """Upscale + boost contrast on retry attempts to improve OCR accuracy."""
        from PIL import Image, ImageEnhance

        image = Image.open(image_path)
        scale = 1.0 + 0.5 * attempt
        resized = image.resize((int(image.width * scale), int(image.height * scale)))
        enhancer = ImageEnhance.Contrast(resized)
        boosted = enhancer.enhance(1.2 + 0.2 * attempt)
        retry_path = image_path.with_name(f"{image_path.stem}_retry{attempt}{image_path.suffix}")
        boosted.save(retry_path)
        return retry_path

    def recognize(self, image_path: Path, languages: list[str] | None = None) -> OCRResult:
        languages = languages or self._settings.ocr_languages
        threshold = self._settings.ocr_confidence_threshold

        best_result: OCRResult | None = None
        current_path = image_path

        try:
            result = self._primary.run(current_path, languages)
            best_result = result
            logger.info("ocr_primary_result", engine=result.engine, confidence=result.confidence)
        except Exception as exc:
            logger.warning("ocr_primary_failed", error=str(exc))
            result = None

        attempt = 0
        while (
            (best_result is None or best_result.confidence < threshold)
            and attempt < self._settings.ocr_max_retries
        ):
            attempt += 1
            try:
                retry_path = self._preprocess_retry(image_path, attempt)
                retry_result = self._primary.run(retry_path, languages)
                logger.info(
                    "ocr_retry_result", attempt=attempt, confidence=retry_result.confidence
                )
                if best_result is None or retry_result.confidence > best_result.confidence:
                    best_result = retry_result
            except Exception as exc:
                logger.warning("ocr_retry_failed", attempt=attempt, error=str(exc))

        if best_result is None or best_result.confidence < threshold:
            try:
                fallback_result = self._fallback.run(image_path, languages)
                logger.info(
                    "ocr_fallback_result",
                    engine=fallback_result.engine,
                    confidence=fallback_result.confidence,
                )
                if best_result is None or fallback_result.confidence > best_result.confidence:
                    best_result = fallback_result
            except Exception as exc:
                logger.error("ocr_fallback_failed", error=str(exc))

        if best_result is None:
            raise RuntimeError(f"OCR failed for {image_path}: all engines raised errors")

        return best_result
