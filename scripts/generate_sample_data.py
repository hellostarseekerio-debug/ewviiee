"""Generates sample data used for manual testing / demos of the Housing
Estate Poster workflow: a poster image with embedded district/estate/
politician text, and an application PDF template with date placeholders.

Run: python scripts/generate_sample_data.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "sample_data"


def make_sample_poster(path: Path) -> None:
    image = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), "觀塘 Kwun Tong", fill="black")
    draw.text((40, 80), "藍田邨 Lam Tin Estate", fill="black")
    draw.text((40, 120), "Housing Poster v2", fill="black")
    draw.text((40, 160), "議員: Chan Tai Man", fill="black")
    draw.rectangle([20, 20, 780, 580], outline="black", width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def make_sample_application_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.setFont("Helvetica", 14)
    c.drawString(72, 760, "Housing Estate Poster Application")
    c.drawString(72, 720, "District: {{DISTRICT}}")
    c.drawString(72, 700, "Estate: {{ESTATE}}")
    c.drawString(72, 680, "Application date: {{APPLICATION_DATE}}")
    c.drawString(72, 660, "Footer date: {{FOOTER_DATE}}")
    c.showPage()
    c.save()


def main() -> None:
    make_sample_poster(SAMPLE_DIR / "dropbox_posters" / "lam_tin_estate_poster_v2.png")
    make_sample_application_pdf(SAMPLE_DIR / "applications" / "lam_tin_estate_application.pdf")
    print(f"Sample data written under {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
