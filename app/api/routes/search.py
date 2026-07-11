from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import SearchResponse
from app.core.database import get_db
from app.search.query import SearchFilters, search_documents

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    estate: str | None = None,
    district: str | None = None,
    workflow_name: str | None = None,
    document_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    keyword: str | None = None,
    ocr_text: str | None = None,
    politician: str | None = None,
    reference_number: str | None = None,
    filename: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    filters = SearchFilters(
        estate=estate,
        district=district,
        workflow_name=workflow_name,
        document_type=document_type,
        date_from=date_from,
        date_to=date_to,
        keyword=keyword,
        ocr_text=ocr_text,
        politician=politician,
        reference_number=reference_number,
        filename=filename,
        limit=limit,
        offset=offset,
    )
    results, total = search_documents(db, filters)
    return SearchResponse(total=total, results=results)
