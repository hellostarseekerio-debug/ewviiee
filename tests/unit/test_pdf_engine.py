from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.pdf_engine.engine import PDFEngine, TextReplacement


def _make_pdf(path: Path, pages_text: list[str]) -> Path:
    c = canvas.Canvas(str(path))
    for text in pages_text:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return path


def test_merge_combines_page_counts(tmp_path):
    pdf_a = _make_pdf(tmp_path / "a.pdf", ["Page A1"])
    pdf_b = _make_pdf(tmp_path / "b.pdf", ["Page B1", "Page B2"])
    output = tmp_path / "merged.pdf"

    PDFEngine(pdf_a).merge([pdf_b], output)

    assert len(PdfReader(str(output)).pages) == 3


def test_split_produces_one_file_per_page(tmp_path):
    pdf = _make_pdf(tmp_path / "multi.pdf", ["One", "Two", "Three"])
    output_dir = tmp_path / "split"

    outputs = PDFEngine(pdf).split(output_dir)

    assert len(outputs) == 3
    for out in outputs:
        assert len(PdfReader(str(out)).pages) == 1


def test_delete_pages_removes_target_index(tmp_path):
    pdf = _make_pdf(tmp_path / "multi.pdf", ["One", "Two", "Three"])
    output = tmp_path / "deleted.pdf"

    PDFEngine(pdf).delete_pages([1], output)

    assert len(PdfReader(str(output)).pages) == 2


def test_rotate_pages_sets_rotation(tmp_path):
    pdf = _make_pdf(tmp_path / "single.pdf", ["Rotate me"])
    output = tmp_path / "rotated.pdf"

    PDFEngine(pdf).rotate_pages(None, 90, output)

    rotated_page = PdfReader(str(output)).pages[0]
    assert rotated_page.get("/Rotate") == 90


def test_replace_text_updates_content_stream(tmp_path):
    pdf = _make_pdf(tmp_path / "template.pdf", ["Application date: {{APPLICATION_DATE}}"])
    output = tmp_path / "filled.pdf"

    PDFEngine(pdf).replace_text(
        [TextReplacement(find="{{APPLICATION_DATE}}", replace="2026-07-11")], output
    )

    text = PdfReader(str(output)).pages[0].extract_text()
    assert "{{APPLICATION_DATE}}" not in text
    assert "2026-07-11" in text
