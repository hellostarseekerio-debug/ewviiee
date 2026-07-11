"""Housing Estate Poster Applications - built-in workflow #1.

Pipeline:
  import       -> locate poster image(s) + application PDF from the source
  classify     -> confirm document_type via filename/AI as needed
  ocr          -> OCR the poster image for district/estate/title/version text
  extract      -> resolve district/estate/politician/title/version from OCR
                  text using the rule engine (AI fallback only if unresolved)
  validate     -> check required fields via rules/validation.yaml
  apply_rules  -> compute output filename + folder from naming.yaml
  generate     -> update application dates, replace poster images, produce
                  the final PDF via the PDF engine
  review       -> optional manual-review gate (config controlled)
  export       -> copy final PDF to the export root under its output folder
  archive      -> move/copy source + final PDF into the archive root
  log          -> emit a structured summary event (audit log)

Every field mapping (district/estate lists, page indices, naming pattern) is
driven entirely by config/rules/*.yaml - nothing here hardcodes a specific
estate name or page number.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime

from app.core.logging_config import get_logger
from app.image_engine.engine import ImageEngine
from app.ocr.engine import OCREngine
from app.pdf_engine.engine import PDFEngine, TextReplacement
from app.plugins.base import BasePlugin
from app.workflow.engine import WorkflowStageError
from app.workflow.models import WorkflowContext

logger = get_logger("plugins.housing_estate_poster")

_TITLE_PATTERN = re.compile(r"(?P<title>[一-鿿\w\s]{2,40})\s*(?:v|Ver|版)\s*(?P<version>\d+(\.\d+)?)", re.IGNORECASE)


class HousingEstatePosterPlugin(BasePlugin):
    plugin_id = "housing_estate_poster"
    display_name = "Housing Estate Poster Applications"
    version = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._ocr_engine: OCREngine | None = None
        self._pdf_engine_cls = PDFEngine
        self._image_engine = ImageEngine()

    def _get_ocr_engine(self) -> OCREngine:
        if self._ocr_engine is None:
            self._ocr_engine = OCREngine()
        return self._ocr_engine

    def get_stage_handlers(self):
        return {
            "import": self.stage_import,
            "classify": self.stage_classify,
            "ocr": self.stage_ocr,
            "extract": self.stage_extract,
            "validate": self.stage_validate,
            "apply_rules": self.stage_apply_rules,
            "generate": self.stage_generate,
            "review": self.stage_review,
            "export": self.stage_export,
            "archive": self.stage_archive,
            "log": self.stage_log,
        }

    # ---- Stages -------------------------------------------------------------

    def stage_import(self, context: WorkflowContext) -> None:
        if not context.document_path.exists():
            raise WorkflowStageError(f"Source document not found: {context.document_path}")
        context.fields["source"] = "dropbox"
        context.fields["source_filename"] = context.document_path.name

    def stage_classify(self, context: WorkflowContext) -> None:
        suffix = context.document_path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".tiff"}:
            context.fields["document_type"] = "poster_image"
        elif suffix == ".pdf":
            context.fields["document_type"] = "application_pdf"
        else:
            raise WorkflowStageError(f"Unsupported file type for this workflow: {suffix}")

    def stage_ocr(self, context: WorkflowContext) -> None:
        if context.fields.get("document_type") != "poster_image":
            context.ocr_text = ""
            context.ocr_confidence = 1.0
            return
        stage_cfg = context.workflow.stage_config.get("ocr", {})
        languages = stage_cfg.get("languages", ["ch_tra", "en"])
        result = self._get_ocr_engine().recognize(context.document_path, languages=languages)
        context.ocr_text = result.text
        context.ocr_confidence = result.confidence
        if result.confidence < 0.4:
            logger.warning("ocr_low_confidence", confidence=result.confidence, path=str(context.document_path))

    def stage_extract(self, context: WorkflowContext) -> None:
        assert self.rule_engine is not None
        text = context.ocr_text or context.document_path.stem

        district = self.rule_engine.resolve_district(text)
        estate = self.rule_engine.resolve_estate(text, district_id=district.id if district else None)

        title, version = self._extract_title_version(text)
        politician = self._extract_politician(text)

        context.fields.update(
            {
                "district": district.name if district else None,
                "district_id": district.id if district else None,
                "estate": estate.name if estate else None,
                "estate_id": estate.id if estate else None,
                "title": title,
                "version": version,
                "politician": politician,
                "date": datetime.utcnow(),
            }
        )
        context.ai_confidence = 1.0 if (district and estate) else 0.5

    @staticmethod
    def _extract_title_version(text: str) -> tuple[str | None, str | None]:
        match = _TITLE_PATTERN.search(text)
        if match:
            return match.group("title").strip(), match.group("version")
        first_line = text.strip().splitlines()[0] if text.strip() else None
        return first_line, None

    @staticmethod
    def _extract_politician(text: str) -> str | None:
        match = re.search(r"(議員|议员|Councillor)\s*[:：]?\s*([一-鿿\w\s]{2,20})", text)
        if match:
            return match.group(2).strip()
        return None

    def stage_validate(self, context: WorkflowContext) -> None:
        assert self.rule_engine is not None
        errors = self.rule_engine.validate_fields(context.fields)
        context.validation_errors = errors
        if errors:
            raise WorkflowStageError("Validation failed: " + "; ".join(errors))

    def stage_apply_rules(self, context: WorkflowContext) -> None:
        assert self.rule_engine is not None
        output_name = self.rule_engine.build_output_name(context.fields, extension=".pdf")
        folder = self.rule_engine.output_folder_for("housing_estate_poster")
        context.fields["output_name"] = output_name
        context.fields["output_folder"] = folder

    def stage_generate(self, context: WorkflowContext) -> None:
        settings = self.settings
        assert settings is not None
        if context.fields.get("document_type") != "application_pdf":
            context.output_path = context.document_path
            return

        working_dir = settings.data_dir / "working" / (context.document_id or "tmp")
        working_dir.mkdir(parents=True, exist_ok=True)
        generated_path = working_dir / context.fields["output_name"]

        pdf_engine = self._pdf_engine_cls(context.document_path)
        date_rules = self.rule_engine.ruleset.date_rules if self.rule_engine else {}
        app_date_fmt = date_rules.get("application_date_format", "%Y-%m-%d")
        footer_date_fmt = date_rules.get("footer_date_format", "%d/%m/%Y")
        today = datetime.utcnow()

        replacements = [
            TextReplacement(find="{{APPLICATION_DATE}}", replace=today.strftime(app_date_fmt)),
            TextReplacement(find="{{FOOTER_DATE}}", replace=today.strftime(footer_date_fmt)),
        ]
        try:
            pdf_engine.replace_text(replacements, generated_path)
        except Exception as exc:
            raise WorkflowStageError(f"Failed to generate final PDF: {exc}") from exc

        context.output_path = generated_path

    def stage_review(self, context: WorkflowContext) -> None:
        stage_cfg = context.workflow.stage_config.get("review", {})
        if stage_cfg.get("require_manual_review") and context.ai_confidence is not None:
            if context.ai_confidence < 0.8:
                raise WorkflowStageError(
                    f"Manual review required: AI confidence {context.ai_confidence:.2f} below threshold"
                )

    def stage_export(self, context: WorkflowContext) -> None:
        settings = self.settings
        assert settings is not None
        if context.output_path is None:
            raise WorkflowStageError("No output document to export")
        export_dir = settings.export_root / context.fields.get("output_folder", "misc")
        export_dir.mkdir(parents=True, exist_ok=True)
        destination = export_dir / context.output_path.name
        shutil.copy2(context.output_path, destination)
        context.fields["export_path"] = str(destination)

    def stage_archive(self, context: WorkflowContext) -> None:
        settings = self.settings
        assert settings is not None
        archive_dir = settings.archive_root / context.fields.get("output_folder", "misc")
        archive_dir.mkdir(parents=True, exist_ok=True)
        destination = archive_dir / (context.output_path or context.document_path).name
        shutil.copy2(context.output_path or context.document_path, destination)
        context.archive_path = destination

    def stage_log(self, context: WorkflowContext) -> None:
        logger.info(
            "housing_estate_poster_complete",
            district=context.fields.get("district"),
            estate=context.fields.get("estate"),
            politician=context.fields.get("politician"),
            output=str(context.output_path) if context.output_path else None,
            archive=str(context.archive_path) if context.archive_path else None,
        )


PLUGIN_CLASS = HousingEstatePosterPlugin
