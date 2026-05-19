from fastapi import APIRouter

from app.api.routes import auth, curriculum, documents, evidence, health, periods, reports


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(curriculum.router, prefix="/curricula", tags=["curriculum"])
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
