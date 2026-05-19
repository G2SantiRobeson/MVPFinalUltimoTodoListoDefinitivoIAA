from app.db.session import SessionLocal
from app.services.analysis import run_period_analysis
from app.services.document_processing import process_document_version


def process_document_task(version_id: str) -> None:
    db = SessionLocal()
    try:
        process_document_version(db, version_id)
    finally:
        db.close()


def run_period_analysis_task(period_id: str) -> dict:
    db = SessionLocal()
    try:
        return run_period_analysis(db, period_id)
    finally:
        db.close()
