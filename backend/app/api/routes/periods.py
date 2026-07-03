import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.models import (
    AcademicPeriod,
    ChunkEmbedding,
    Curriculum,
    Document,
    DocumentChunk,
    DocumentVersion,
    EvaluationResult,
    Evidence,
    ProcessingJob,
    Report,
)
from app.db.session import SessionLocal, get_db
from app.schemas.api import AnalysisOut, CellDetailOut, PeriodCreate, PeriodOut, RunAnalysisOut
from app.services.analysis import build_cell_detail, build_period_analysis, run_period_analysis
from app.services.locks import document_processing_lock
from app.services.progress import get_analysis_progress


router = APIRouter()


def _run_analysis_in_background(period_id: str) -> None:
    db = SessionLocal()
    try:
        run_period_analysis(db, period_id)
    except Exception as exc:
        db.rollback()
        period = db.get(AcademicPeriod, period_id)
        if period:
            period.status = "warning"
            period.updated_at = datetime.utcnow()
            db.commit()
        print(f"[IAAPLICADA] Periodo {period_id}: analisis fallido: {exc}", flush=True)
    finally:
        db.close()


def _format_dt(value: datetime | None) -> str:
    return value.strftime("%d %b %Y") if value else "Sin analisis"


def _period_payload(db: Session, period: AcademicPeriod) -> dict:
    documents = (
        db.query(Document)
        .filter(Document.period_id == period.id, Document.status != "deleted")
        .order_by(Document.created_at.desc())
        .all()
    )
    thesis = [
        [
            document.title,
            document.versions[-1].page_count if document.versions else 0,
            document.status,
            document.id,
        ]
        for document in documents
    ]
    curriculum = db.get(Curriculum, period.curriculum_id) if period.curriculum_id else None
    return {
        "id": period.id,
        "name": period.name,
        "curriculum_id": curriculum.id if curriculum else None,
        "curriculum_name": (curriculum.display_name or curriculum.version) if curriculum else "",
        "program": curriculum.program.name if curriculum else "",
        "status": period.status,
        "analyzedAt": _format_dt(period.analyzed_at),
        "updatedAt": _format_dt(period.updated_at),
        "metrics": {
            "thesis": len(documents),
            "recall": 0,
            "automation": 0,
        },
        "thesis": thesis,
    }


@router.get("", response_model=list[PeriodOut])
def list_periods(db: Session = Depends(get_db)) -> list[dict]:
    periods = (
        db.query(AcademicPeriod)
        .filter(AcademicPeriod.status != "deleted")
        .order_by(AcademicPeriod.name.desc())
        .all()
    )
    return [_period_payload(db, period) for period in periods]


@router.post("", response_model=PeriodOut)
def create_period(
    payload: PeriodCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("academic_admin", "technical_admin")),
) -> dict:
    curriculum = db.get(Curriculum, payload.curriculum_id)
    if not curriculum:
        raise HTTPException(status_code=404, detail="Matriz de traza no encontrada.")

    existing = (
        db.query(AcademicPeriod)
        .filter(
            AcademicPeriod.name == payload.name,
            AcademicPeriod.curriculum_id == payload.curriculum_id,
        )
        .first()
    )
    if existing:
        if existing.status == "deleted":
            existing.status = "empty"
            existing.analyzed_at = None
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
        return _period_payload(db, existing)
    period = AcademicPeriod(
        name=payload.name,
        curriculum_id=payload.curriculum_id,
        status="empty",
        updated_at=datetime.utcnow(),
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return _period_payload(db, period)


@router.delete("/{period_id}")
def delete_period(
    period_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("academic_admin", "technical_admin")),
) -> dict:
    """Elimina un periodo y todos sus datos asociados."""
    period = db.get(AcademicPeriod, period_id)
    if not period or period.status == "deleted":
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")

    with document_processing_lock:
        return _delete_period_data(db, period_id, period)


def _delete_period_data(db: Session, period_id: str, period: AcademicPeriod) -> dict:
    document_ids = [
        document_id
        for (document_id,) in db.query(Document.id).filter(Document.period_id == period_id).all()
    ]
    version_ids = []
    file_paths: list[Path] = []
    if document_ids:
        versions = db.query(DocumentVersion).filter(DocumentVersion.document_id.in_(document_ids)).all()
        version_ids = [version.id for version in versions]
        file_paths = [Path(version.file_uri) for version in versions if version.file_uri]

    chunk_ids = []
    if version_ids:
        chunk_ids = [
            chunk_id
            for (chunk_id,) in db.query(DocumentChunk.id)
            .filter(DocumentChunk.version_id.in_(version_ids))
            .all()
        ]

    db.query(Evidence).filter(Evidence.period_id == period_id).delete(synchronize_session=False)
    db.query(EvaluationResult).filter(EvaluationResult.period_id == period_id).delete(
        synchronize_session=False
    )
    db.query(Report).filter(Report.period_id == period_id).delete(synchronize_session=False)

    if chunk_ids:
        db.query(Evidence).filter(Evidence.chunk_id.in_(chunk_ids)).delete(synchronize_session=False)
        db.query(ChunkEmbedding).filter(ChunkEmbedding.chunk_id.in_(chunk_ids)).delete(
            synchronize_session=False
        )

    if version_ids:
        db.query(DocumentChunk).filter(DocumentChunk.version_id.in_(version_ids)).delete(
            synchronize_session=False
        )
        db.query(ProcessingJob).filter(ProcessingJob.version_id.in_(version_ids)).delete(
            synchronize_session=False
        )
        db.query(DocumentVersion).filter(DocumentVersion.id.in_(version_ids)).delete(
            synchronize_session=False
        )

    if document_ids:
        db.query(Document).filter(Document.id.in_(document_ids)).delete(synchronize_session=False)

    db.delete(period)
    db.commit()

    removed_files = 0
    period_dirs = {file_path.parent.parent for file_path in file_paths}
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                removed_files += 1
            document_dir = file_path.parent
            if document_dir.exists() and not any(document_dir.iterdir()):
                shutil.rmtree(document_dir, ignore_errors=True)
        except OSError:
            pass

    for period_dir in period_dirs:
        try:
            if period_dir.exists() and not any(period_dir.iterdir()):
                shutil.rmtree(period_dir, ignore_errors=True)
        except OSError:
            pass

    return {"id": period_id, "status": "deleted", "removed_files": removed_files}


@router.get("/{period_id}/analysis", response_model=AnalysisOut)
def get_analysis(period_id: str, db: Session = Depends(get_db)) -> dict:
    """Obtiene el análisis completo de un período: celdas, métricas y brechas."""
    period = db.get(AcademicPeriod, period_id)
    if not period or period.status == "deleted":
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    return build_period_analysis(db, period_id)


@router.get("/{period_id}/analysis/cell-detail", response_model=CellDetailOut)
def get_cell_detail(
    period_id: str,
    course_id: str,
    competency_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Obtiene el detalle trazable de una celda curso-competencia del heatmap."""
    try:
        return build_cell_detail(db, period_id, course_id, competency_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{period_id}/analysis/run", response_model=RunAnalysisOut)
def run_analysis(
    period_id: str,
    background_tasks: BackgroundTasks,
    background: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("evaluator", "academic_admin", "technical_admin")),
) -> dict:
    """Ejecuta (o encola) el análisis semántico de un período académico."""
    period = db.get(AcademicPeriod, period_id)
    if not period or period.status == "deleted":
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    if background:
        period.status = "processing"
        period.updated_at = datetime.utcnow()
        db.commit()
        background_tasks.add_task(_run_analysis_in_background, period_id)
        return {
            "period_id": period_id,
            "status": "processing",
            "message": "Analisis iniciado.",
            "metrics": {},
        }
    metrics = run_period_analysis(db, period_id)
    return {
        "period_id": period_id,
        "status": "ready" if metrics["evaluated_cells"] else "warning",
        "message": "Analisis generado con evidencia trazable."
        if metrics["evaluated_cells"]
        else "No hay chunks procesados para este periodo.",
        "metrics": metrics,
    }


@router.get("/{period_id}/analysis/progress")
def analysis_progress(
    period_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("evaluator", "academic_admin", "technical_admin")),
) -> dict:
    """Retorna el progreso del análisis en ejecución para un período."""
    period = db.get(AcademicPeriod, period_id)
    if not period or period.status == "deleted":
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    return get_analysis_progress(period_id)
