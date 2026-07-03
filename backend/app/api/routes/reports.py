from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.models import Report
from app.db.session import get_db
from app.schemas.api import ReportOut
from app.services.excel_export import export_periods_to_excel


router = APIRouter()

REPORT_LIST_LIMIT = 50
EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXCEL_FILENAME = "Reporte_Validacion_Perfil_Egreso.xlsx"


@router.get("/excel")
def download_excel(period_id: str | None = None, db: Session = Depends(get_db)) -> Response:
    period_ids = [period_id] if period_id else None
    excel_bytes = export_periods_to_excel(db, period_ids)

    headers = {"Content-Disposition": f'attachment; filename="{EXCEL_FILENAME}"'}
    return Response(
        content=excel_bytes,
        media_type=EXCEL_MEDIA_TYPE,
        headers=headers,
    )


@router.get("", response_model=list[ReportOut])
def list_reports(period_id: str | None = None, db: Session = Depends(get_db)) -> list[Report]:
    query = db.query(Report).order_by(Report.created_at.desc())
    if period_id:
        query = query.filter(Report.period_id == period_id)
    return query.limit(REPORT_LIST_LIMIT).all()
