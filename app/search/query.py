"""Document search: builds a filtered, paginated SQLAlchemy query over
Document rows. Every field the spec calls out (estate, district, workflow,
document type, date range, keyword, OCR text, politician, reference number,
filename) is a supported filter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.models import Document


@dataclass
class SearchFilters:
    estate: str | None = None
    district: str | None = None
    workflow_name: str | None = None
    document_type: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    keyword: str | None = None
    ocr_text: str | None = None
    politician: str | None = None
    reference_number: str | None = None
    filename: str | None = None
    limit: int = 50
    offset: int = 0


def search_documents(session: Session, filters: SearchFilters) -> tuple[list[Document], int]:
    query = session.query(Document)

    if filters.estate:
        query = query.filter(Document.estate.ilike(f"%{filters.estate}%"))
    if filters.district:
        query = query.filter(Document.district.ilike(f"%{filters.district}%"))
    if filters.workflow_name:
        query = query.filter(Document.workflow_name == filters.workflow_name)
    if filters.document_type:
        query = query.filter(Document.document_type == filters.document_type)
    if filters.date_from:
        query = query.filter(Document.document_date >= filters.date_from)
    if filters.date_to:
        query = query.filter(Document.document_date <= filters.date_to)
    if filters.politician:
        query = query.filter(Document.politician.ilike(f"%{filters.politician}%"))
    if filters.reference_number:
        query = query.filter(Document.reference_number.ilike(f"%{filters.reference_number}%"))
    if filters.filename:
        query = query.filter(Document.filename.ilike(f"%{filters.filename}%"))
    if filters.ocr_text:
        query = query.filter(Document.ocr_text.ilike(f"%{filters.ocr_text}%"))
    if filters.keyword:
        like = f"%{filters.keyword}%"
        query = query.filter(
            or_(
                Document.title.ilike(like),
                Document.ocr_text.ilike(like),
                Document.filename.ilike(like),
            )
        )

    total = query.count()
    results = (
        query.order_by(Document.created_at.desc())
        .offset(filters.offset)
        .limit(filters.limit)
        .all()
    )
    return results, total
