from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.embeddings import EmbeddingService


router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Verifica que la API esté operativa."""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ai-status")
def ai_status() -> dict:
    """Retorna el estado del servicio de embeddings (proveedor, modelo, dispositivo)."""
    service = EmbeddingService()
    return service.info()
