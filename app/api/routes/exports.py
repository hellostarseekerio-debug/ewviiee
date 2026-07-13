"""Background export job status/download - generic across resource types
(ExportJob.resource_type is stored per-job, see app/core/models.py), even
though Posters are the only caller today (POST /api/posters/export/zip).
Job *creation* lives on the resource's own route (e.g. posters.py) since
that's where the resource-specific filter logic already is; this module
only tracks and serves the result.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import ExportJobOut
from app.core.database import get_db
from app.core.models import ExportJob, ExportJobStatus

router = APIRouter(prefix="/api/export-jobs", tags=["exports"])


@router.get("/{job_id}", response_model=ExportJobOut)
def get_export_job(job_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    job = db.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export job not found")
    return job


@router.get("/{job_id}/download")
def download_export_job(job_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    job = db.get(ExportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export job not found")
    if job.status != ExportJobStatus.COMPLETED or not job.file_path:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Export is not ready yet (status: {job.status.value})")
    path = Path(job.file_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_409_CONFLICT, "Export file is missing on disk")
    return FileResponse(path, filename=f"export_{job.id}.zip", media_type="application/zip")
