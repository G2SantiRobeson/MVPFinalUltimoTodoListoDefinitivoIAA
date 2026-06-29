from fastapi import APIRouter

from app.services.embeddings import EmbeddingService


router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """Verifica que la API esté operativa."""
    return {"status": "ok"}


@router.get("/ai-status")
def ai_status() -> dict:
    """Retorna el estado del servicio de embeddings (proveedor, modelo, dispositivo)."""
    service = EmbeddingService()
    return service.info()
