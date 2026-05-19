from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AcademicPeriod,
    Competency,
    Course,
    CourseCompetency,
    Curriculum,
    EvaluationCriterion,
    Program,
    Role,
    User,
)
from app.services.curriculum_loader import load_matrix_from_xlsx


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

    for period_name in PERIODS:
        if not db.query(AcademicPeriod).filter(AcademicPeriod.name == period_name).first():
            db.add(AcademicPeriod(name=period_name, status="empty", updated_at=datetime.utcnow()))

    program = db.query(Program).filter(Program.name == "Ingenieria Civil en Computacion").first()
    if not program:
        program = Program(name="Ingenieria Civil en Computacion")
        db.add(program)
        db.flush()

    curriculum = (
        db.query(Curriculum)
        .filter(
            Curriculum.program_id == program.id,
            Curriculum.year == 2025,
            Curriculum.version == "PE 2025 COMPUTACION",
        )
        .first()
    )
    if not curriculum:
        curriculum = Curriculum(program_id=program.id, year=2025, version="PE 2025 COMPUTACION")
        db.add(curriculum)
        db.flush()

    if db.query(Competency).filter(Competency.curriculum_id == curriculum.id).count() == 0:
        matrix = load_matrix_from_xlsx(get_settings().curriculum_xlsx_path)
        competencies: list[Competency] = []
        for item in matrix.competencies:
            competency = Competency(
                curriculum_id=curriculum.id,
                code=item.code,
                group=item.group,
                description=item.description,
                sort_order=item.sort_order,
            )
            db.add(competency)
            db.flush()
            db.add(
                EvaluationCriterion(
                    competency_id=competency.id,
                    name=f"Evidencia para {item.code}",
                    description=item.description,
                    threshold=get_settings().evidence_threshold,
                )
            )
            competencies.append(competency)

        for item in matrix.courses:
            course = Course(
                curriculum_id=curriculum.id,
                code=item.code,
                title=item.title,
                semester=item.semester,
                sort_order=item.sort_order,
            )
            db.add(course)
            db.flush()
            for competency_index in item.competency_indexes:
                db.add(
                    CourseCompetency(
                        course_id=course.id,
                        competency_id=competencies[competency_index].id,
                    )
                )

    db.commit()
