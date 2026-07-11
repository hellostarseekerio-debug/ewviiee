from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import DocumentOut
from app.core.database import get_db
from app.core.models import Document

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    return (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
