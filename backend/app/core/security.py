from collections.abc import Iterable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db


DEMO_TOKENS = {
    "demo-student": "estudiante@demo.local",
    "demo-professor": "profesor@demo.local",
    "demo-evaluator": "evaluador@demo.local",
    "demo-academic-admin": "academico@demo.local",
    "demo-tech-admin": "tecnico@demo.local",
}
DEFAULT_DEMO_TOKEN = "demo-academic-admin"


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Obtiene el usuario autenticado a partir del token Bearer.

    Args:
        authorization: Encabezado Authorization (Bearer token).
        db: Sesión de base de datos.

    Returns:
        Objeto User correspondiente al token.

    Raises:
        HTTPException 401: Si el token es inválido o el usuario no existe.
    """
    token = DEFAULT_DEMO_TOKEN
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    email = DEMO_TOKENS.get(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o ausente.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario demo no existe.",
        )
    return user


def require_roles(*allowed_roles: str):
    """Dependencia de FastAPI que restringe acceso por roles.

    Args:
        *allowed_roles: Roles que tienen permiso para acceder al endpoint.

    Returns:
        Función dependencia que retorna el usuario si tiene rol autorizado.

    Raises:
        HTTPException 403: Si el usuario no posee ninguno de los roles requeridos.
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        role_names = {role.name for role in current_user.roles}
        if role_names.intersection(set(allowed_roles)):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permiso insuficiente. Roles requeridos: {', '.join(allowed_roles)}.",
        )

    return dependency


def has_any_role(user: User, roles: Iterable[str]) -> bool:
    return bool({role.name for role in user.roles}.intersection(set(roles)))
