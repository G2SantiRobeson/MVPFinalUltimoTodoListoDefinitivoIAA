from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_roles
from app.db.models import Curriculum
from app.db.session import get_db
from app.schemas.api import CurriculumSummaryOut, MatrixOut
from app.services.curriculum_matrices import (
    import_curriculum_matrix,
    list_curricula_payload,
    matrix_payload,
)


router = APIRouter()


@router.get("", response_model=list[CurriculumSummaryOut])
def list_curricula(db: Session = Depends(get_db)) -> list[dict]:
    return list_curricula_payload(db)


@router.post("", response_model=CurriculumSummaryOut, status_code=status.HTTP_201_CREATED)
async def upload_curriculum_matrix(
    display_name: str = Form(..., min_length=2, max_length=160),
    program: str = Form(..., min_length=2, max_length=220),
    year: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("academic_admin", "technical_admin")),
) -> dict:
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="La matriz debe ser un archivo .xlsx.")

    target_dir = (
        get_settings().storage_dir
        / "matrices"
        / datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(await file.read())

    try:
        curriculum = import_curriculum_matrix(
            db,
            target_path,
            display_name=display_name,
            program_name=program,
            year=year,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"No se pudo cargar la matriz: {exc}") from exc

    return _curriculum_summary(curriculum)


@router.get("/current/matrix", response_model=MatrixOut)
def current_matrix(db: Session = Depends(get_db)) -> dict:
    curriculum = db.query(Curriculum).order_by(Curriculum.year.desc()).first()
    if not curriculum:
        raise HTTPException(status_code=404, detail="No existe una malla cargada.")
    return matrix_payload(db, curriculum)


@router.get("/{curriculum_id}/matrix", response_model=MatrixOut)
def get_matrix(curriculum_id: str, db: Session = Depends(get_db)) -> dict:
    curriculum = db.get(Curriculum, curriculum_id)
    if not curriculum:
        raise HTTPException(status_code=404, detail="Matriz no encontrada.")
    return matrix_payload(db, curriculum)


def _curriculum_summary(curriculum: Curriculum) -> dict:
    return {
        "id": curriculum.id,
        "display_name": curriculum.display_name or curriculum.version,
        "program": curriculum.program.name,
        "year": curriculum.year,
        "version": curriculum.version,
        "source_filename": curriculum.source_filename or "",
    }
