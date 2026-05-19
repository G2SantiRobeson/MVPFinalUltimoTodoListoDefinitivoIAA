from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.models import Report
from app.db.session import get_db
from app.schemas.api import ReportOut
from app.services.excel_export import export_periods_to_excel


router = APIRouter()


@router.get("/excel")
def download_excel(period_id: str | None = None, db: Session = Depends(get_db)):
    period_ids = [period_id] if period_id else None
    excel_bytes = export_periods_to_excel(db, period_ids)
    
    headers = {
        "Content-Disposition": 'attachment; filename="Reporte_Validacion_Perfil_Egreso.xlsx"'
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )


@router.get("", response_model=list[ReportOut])
def list_reports(period_id: str | None = None, db: Session = Depends(get_db)) -> list[Report]:
    query = db.query(Report).order_by(Report.created_at.desc())
    if period_id:
        query = query.filter(Report.period_id == period_id)
    return query.limit(50).all()
