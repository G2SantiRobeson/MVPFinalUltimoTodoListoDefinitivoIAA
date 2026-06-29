from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.db.models import AcademicPeriod, Curriculum, Document
from app.db.session import SessionLocal, get_db
from app.schemas.api import AnalysisOut, CellDetailOut, PeriodCreate, PeriodOut, RunAnalysisOut
from app.services.analysis import build_cell_detail, build_period_analysis, run_period_analysis
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
    periods = db.query(AcademicPeriod).order_by(AcademicPeriod.name.desc()).all()
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


@router.get("/{period_id}/analysis", response_model=AnalysisOut)
def get_analysis(period_id: str, db: Session = Depends(get_db)) -> dict:
    """Obtiene el análisis completo de un período: celdas, métricas y brechas."""
    if not db.get(AcademicPeriod, period_id):
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
    if not period:
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
    if not db.get(AcademicPeriod, period_id):
        raise HTTPException(status_code=404, detail="Periodo no encontrado.")
    return get_analysis_progress(period_id)
