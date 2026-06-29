from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import (
    AcademicPeriod,
    Curriculum,
    Role,
    User,
)
from app.services.curriculum_matrices import import_initial_curricula


ROLE_DESCRIPTIONS = {
    "student": "Sube memorias y consulta sus resultados autorizados.",
    "professor": "Revisa memorias de estudiantes asociados.",
    "evaluator": "Valida evidencias, resultados y reportes academicos.",
    "academic_admin": "Administra periodos, mallas, criterios y reportes.",
    "technical_admin": "Administra configuracion, jobs, logs e infraestructura.",
}

DEMO_USERS = [
    ("Estudiante Demo", "estudiante@demo.local", "student"),
    ("Profesor Guia Demo", "profesor@demo.local", "professor"),
    ("Evaluador Demo", "evaluador@demo.local", "evaluator"),
    ("Administrador Academico Demo", "academico@demo.local", "academic_admin"),
    ("Administrador Tecnico Demo", "tecnico@demo.local", "technical_admin"),
]

PERIODS = ["2025-2", "2025-1", "2024-2"]


def seed_demo_data(db: Session) -> None:
    roles: dict[str, Role] = {}
    for name, description in ROLE_DESCRIPTIONS.items():
        role = db.query(Role).filter(Role.name == name).first()
        if not role:
            role = Role(name=name, description=description)
            db.add(role)
        roles[name] = role

    for name, email, role_name in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(name=name, email=email)
            user.roles.append(roles[role_name])
            db.add(user)

    curricula = import_initial_curricula(db)
    default_curriculum = _default_curriculum(db, curricula)

    for period_name in PERIODS:
        period = db.query(AcademicPeriod).filter(AcademicPeriod.name == period_name).first()
        if not period:
            period = AcademicPeriod(
                name=period_name,
                curriculum_id=default_curriculum.id if default_curriculum else None,
                status="empty",
                updated_at=datetime.utcnow(),
            )
            db.add(period)
        elif not period.curriculum_id and default_curriculum:
            period.curriculum_id = default_curriculum.id

    db.commit()


def _default_curriculum(db: Session, imported: list[Curriculum]) -> Curriculum | None:
    for curriculum in imported:
        if "COMPUTACION" in (curriculum.version or "").upper():
            return curriculum
    return db.query(Curriculum).order_by(Curriculum.year.desc()).first()
