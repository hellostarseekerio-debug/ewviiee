"""PDF manipulation engine.

Built on pikepdf (qpdf bindings) for structural edits that must preserve
fonts/layout/transparency, and pypdf for page-level operations. Nothing here
rasterizes a page unless `rasterize=True` is explicitly passed - vector text,
fonts and images are edited/replaced in place.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pikepdf
from pypdf import PdfReader, PdfWriter


@dataclass
class TextReplacement:
    find: str
    replace: str


class PDFEngine:
    """High-level operations over a single PDF, used by the workflow/plugin layer."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    # ---- Page operations -------------------------------------------------

    def merge(self, other_paths: list[Path], output_path: Path) -> Path:
        writer = PdfWriter()
        for p in [self.path, *other_paths]:
            writer.append(PdfReader(str(p)))
        self._write(writer, output_path)
        return output_path

    def split(self, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        reader = PdfReader(str(self.path))
        outputs = []
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            out_path = output_dir / f"{self.path.stem}_p{i + 1}.pdf"
            self._write(writer, out_path)
            outputs.append(out_path)
        return outputs

    def insert_pages(self, insert_paths: list[Path], at_index: int, output_path: Path) -> Path:
        reader = PdfReader(str(self.path))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i == at_index:
                for insert_path in insert_paths:
                    for insert_page in PdfReader(str(insert_path)).pages:
                        writer.add_page(insert_page)
            writer.add_page(page)
        self._write(writer, output_path)
        return output_path

    def delete_pages(self, indices: list[int], output_path: Path) -> Path:
        reader = PdfReader(str(self.path))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i not in indices:
                writer.add_page(page)
        self._write(writer, output_path)
        return output_path

    def rotate_pages(self, indices: list[int] | None, degrees: int, output_path: Path) -> Path:
        reader = PdfReader(str(self.path))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if indices is None or i in indices:
                page.rotate(degrees)
            writer.add_page(page)
        self._write(writer, output_path)
        return output_path

    def compress(self, output_path: Path, image_quality: int = 60) -> Path:
        with pikepdf.open(str(self.path)) as pdf:
            for page in pdf.pages:
                for image_key in list(page.images.keys()):
                    try:
                        raw_image = page.images[image_key]
                        pdf_image = pikepdf.PdfImage(raw_image)
                        pdf_image.obj.write(
                            pdf_image.read_bytes(), filter=pikepdf.Name("/DCTDecode")
                        )
                    except Exception:
                        continue
            pdf.save(str(output_path), linearize=True)
        return output_path

    # ---- Content editing ---------------------------------------------------

    def replace_text(self, replacements: list[TextReplacement], output_path: Path) -> Path:
        """Replace literal text runs in content streams, preserving font/layout.

        This performs a direct content-stream string substitution via pikepdf,
        which keeps the original font/positioning operators intact. Suitable for
        short token replacements (dates, reference numbers, names) as used by
        the Housing Estate Poster workflow.
        """
        with pikepdf.open(str(self.path)) as pdf:
            for page in pdf.pages:
                if "/Contents" not in page:
                    continue
                content = pikepdf.parse_content_stream(page)
                changed = False
                new_instructions = []
                for operands, operator in content:
                    operands = list(operands)
                    if operator == pikepdf.Operator("Tj") and operands:
                        text = str(operands[0])
                        new_text = text
                        for rep in replacements:
                            if rep.find in new_text:
                                new_text = new_text.replace(rep.find, rep.replace)
                        if new_text != text:
                            operands[0] = pikepdf.String(new_text)
                            changed = True
                    new_instructions.append((operands, operator))
                if changed:
                    new_stream = pikepdf.unparse_content_stream(new_instructions)
                    page.Contents = pdf.make_stream(new_stream)
            pdf.save(str(output_path))
        return output_path

    def replace_image(
        self, image_index: int, new_image_path: Path, output_path: Path, page_index: int = 0
    ) -> Path:
        """Swap an embedded raster image XObject for a new image, keeping the
        original placement/transform matrix so layout is preserved."""
        with pikepdf.open(str(self.path)) as pdf:
            page = pdf.pages[page_index]
            image_keys = list(page.images.keys())
            if image_index >= len(image_keys):
                raise IndexError(f"Page {page_index} has only {len(image_keys)} images")
            target_key = image_keys[image_index]
            from PIL import Image as PILImage

            pil_image = PILImage.open(new_image_path)
            new_xobject = pikepdf.PdfImage.from_pil_image(pdf, pil_image)
            page.images[target_key].write(new_xobject.read_bytes())
            for attr in ("Width", "Height", "ColorSpace", "BitsPerComponent", "Filter"):
                if attr in new_xobject.obj:
                    page.images[target_key][attr] = new_xobject.obj[attr]
            pdf.save(str(output_path))
        return output_path

    # ---- Forms --------------------------------------------------------------

    def fill_form(self, field_values: dict[str, str], output_path: Path, flatten: bool = False) -> Path:
        reader = PdfReader(str(self.path))
        writer = PdfWriter()
        writer.append(reader)
        for page in writer.pages:
            writer.update_page_form_field_values(page, field_values)
        if flatten:
            writer.set_need_appearances_writer(False)
        self._write(writer, output_path)
        return output_path

    @staticmethod
    def _write(writer: PdfWriter, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            writer.write(f)
