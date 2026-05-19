from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.models import User
from app.schemas.api import UserOut


router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/demo-tokens")
def demo_tokens() -> dict:
    return {
        "student": "demo-student",
        "professor": "demo-professor",
        "evaluator": "demo-evaluator",
        "academic_admin": "demo-academic-admin",
        "technical_admin": "demo-tech-admin",
    }
