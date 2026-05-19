from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.db.models import AcademicPeriod, Document, DocumentVersion, ProcessingJob, User
from app.db.session import SessionLocal, get_db
from app.schemas.api import DocumentOut, ProcessingJobOut
from app.services.document_processing import process_document_version
from app.services.locks import sqlite_write_lock
from app.services.storage import store_upload


router = APIRouter()


def _process_in_background(version_id: str) -> None:
    db = SessionLocal()
    try:
        process_document_version(db, version_id)
    finally:
        db.close()


@router.get("", response_model=list[DocumentOut])
def list_documents(period_id: str | None = None, db: Session = Depends(get_db)) -> list[Document]:
    query = db.query(Document).filter(Document.status != "deleted").order_by(Document.created_at.desc())
    if period_id:
        query = query.filter(Document.period_id == period_id)
    return query.all()


@router.post("", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    period_id: str = Form(...),
    title: str | None = Form(default=None),
    author: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student", "professor", "academic_admin")),
) -> Document:
    period = db.get(AcademicPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")

    document = Document(
        period_id=period_id,
        owner_id=current_user.id,
        title=title or Path(file.filename or "Memoria").stem,
        author=author or current_user.name,
        status="uploaded",
        updated_at=datetime.utcnow(),
    )
    db.add(document)
    db.flush()
    file_uri, checksum, _size = await store_upload(file, period_id, document.id)
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_uri=file_uri,
        original_filename=file.filename or Path(file_uri).name,
        checksum=checksum,
        mime_type=file.content_type or "",
        uploaded_by_id=current_user.id,
    )
    db.add(version)
    period.status = "warning"
    period.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(document)

    background_tasks.add_task(_process_in_background, version.id)
    return document


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    document = db.get(Document, document_id)
    if not document or document.status == "deleted":
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("student", "professor", "academic_admin", "technical_admin")),
) -> dict:
    with sqlite_write_lock:
        document = db.get(Document, document_id)
        if not document or document.status == "deleted":
            raise HTTPException(status_code=404, detail="Documento no encontrado.")

        document.status = "deleted"
        document.updated_at = datetime.utcnow()
        document.period.status = "warning"
        document.period.updated_at = datetime.utcnow()
        db.commit()
    return {"id": document_id, "status": "deleted"}


@router.get("/{document_id}/processing-status", response_model=list[ProcessingJobOut])
def processing_status(
    document_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[ProcessingJob]:
    document = db.get(Document, document_id)
    if not document or document.status == "deleted":
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    version_ids = [version.id for version in document.versions]
    if not version_ids:
        return []
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.version_id.in_(version_ids))
        .order_by(ProcessingJob.started_at.desc())
        .all()
    )
