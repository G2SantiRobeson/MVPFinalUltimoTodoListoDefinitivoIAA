from fastapi import APIRouter

from app.services.embeddings import EmbeddingService


router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@router.get("/ai-status")
def ai_status() -> dict:
    service = EmbeddingService()
    return service.info()
