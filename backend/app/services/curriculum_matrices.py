from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    Competency,
    Course,
    CourseCompetency,
    Curriculum,
    EvaluationCriterion,
    Program,
)
from app.schemas.api import CourseOut
from app.services.curriculum_loader import load_matrix_from_xlsx


PROGRAM_ALIASES = {
    "AMBIENTAL": "Ingenieria Civil Ambiental",
    "COMPUTACION": "Ingenieria Civil en Computacion",
    "COMPUTACIÓN": "Ingenieria Civil en Computacion",
    "ELECTRICA": "Ingenieria Civil Electrica",
    "ELÉCTRICA": "Ingenieria Civil Electrica",
    "INDUSTRIAL": "Ingenieria Civil Industrial",
    "QUIMICA": "Ingenieria Civil Quimica",
    "QUÍMICA": "Ingenieria Civil Quimica",
}


def _clean_matrix_name(raw_name: str) -> str:
    name = Path(raw_name).stem.strip()
    name = re.sub(r"\s*\(\d+\)$", "", name)
    name = re.sub(r"^matriz\s+(de\s+)?tributaci[oó]n\s*", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip() or Path(raw_name).stem.strip()


def _infer_year(text: str) -> int:
    match = re.search(r"\b(20\d{2})\b", text)
    return int(match.group(1)) if match else datetime.utcnow().year


def _infer_program(text: str) -> str:
    normalized = text.upper()
    for token, program_name in PROGRAM_ALIASES.items():
        if token in normalized:
            return program_name
    return "Carrera no especificada"


def _matrix_version(display_name: str) -> str:
    version = re.sub(r"\s+", " ", display_name.upper()).strip()
    return version[:80] or f"MATRIZ {datetime.utcnow().year}"


def _curriculum_display_name(curriculum: Curriculum) -> str:
    return curriculum.display_name or curriculum.version


def resolve_initial_matrix_paths() -> list[Path]:
    settings = get_settings()
    candidates: list[Path] = []
    if settings.curriculum_xlsx_path.exists():
        candidates.append(settings.curriculum_xlsx_path)
    candidates.extend(sorted(settings.matrices_dir.glob("*.xlsx")))

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(path)
    return unique_paths


def import_curriculum_matrix(
    db: Session,
    path: Path,
    display_name: str | None = None,
    program_name: str | None = None,
    year: int | None = None,
) -> Curriculum:
    matrix = load_matrix_from_xlsx(path)
    matrix_name = (display_name or _clean_matrix_name(path.name)).strip()
    program_label = (program_name or _infer_program(matrix_name)).strip()
    matrix_year = year or _infer_year(matrix_name)
    version = _matrix_version(matrix_name)

    program = db.query(Program).filter(Program.name == program_label).first()
    if not program:
        program = Program(name=program_label)
        db.add(program)
        db.flush()

    curriculum = (
        db.query(Curriculum)
        .filter(
            Curriculum.program_id == program.id,
            Curriculum.year == matrix_year,
            Curriculum.version == version,
        )
        .first()
    )
    if not curriculum:
        curriculum = Curriculum(
            program_id=program.id,
            year=matrix_year,
            version=version,
            display_name=matrix_name,
            source_filename=path.name,
        )
        db.add(curriculum)
        db.flush()
    else:
        curriculum.display_name = curriculum.display_name or matrix_name
        curriculum.source_filename = curriculum.source_filename or path.name

    has_competencies = (
        db.query(Competency).filter(Competency.curriculum_id == curriculum.id).count() > 0
    )
    if has_competencies:
        return curriculum

    settings = get_settings()
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
                threshold=settings.evidence_threshold,
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
            if competency_index < len(competencies):
                db.add(
                    CourseCompetency(
                        course_id=course.id,
                        competency_id=competencies[competency_index].id,
                    )
                )

    return curriculum


def import_initial_curricula(db: Session) -> list[Curriculum]:
    curricula = [import_curriculum_matrix(db, path) for path in resolve_initial_matrix_paths()]
    return curricula


def list_curricula_payload(db: Session) -> list[dict]:
    curricula = (
        db.query(Curriculum)
        .join(Program)
        .order_by(Program.name.asc(), Curriculum.year.desc(), Curriculum.display_name.asc())
        .all()
    )
    return [
        {
            "id": curriculum.id,
            "display_name": _curriculum_display_name(curriculum),
            "program": curriculum.program.name,
            "year": curriculum.year,
            "version": curriculum.version,
            "source_filename": curriculum.source_filename or "",
        }
        for curriculum in curricula
    ]


def matrix_payload(db: Session, curriculum: Curriculum) -> dict:
    competencies = (
        db.query(Competency)
        .filter(Competency.curriculum_id == curriculum.id)
        .order_by(Competency.sort_order)
        .all()
    )
    competency_index = {competency.id: index for index, competency in enumerate(competencies)}
    links = (
        db.query(CourseCompetency)
        .join(Course)
        .filter(Course.curriculum_id == curriculum.id)
        .all()
    )
    links_by_course: dict[str, list[int]] = {}
    for link in links:
        if link.competency_id in competency_index:
            links_by_course.setdefault(link.course_id, []).append(
                competency_index[link.competency_id]
            )

    courses = (
        db.query(Course)
        .filter(Course.curriculum_id == curriculum.id)
        .order_by(Course.sort_order)
        .all()
    )

    return {
        "curriculum_id": curriculum.id,
        "program": curriculum.program.name,
        "version": curriculum.version,
        "display_name": _curriculum_display_name(curriculum),
        "competencies": [
            {
                "db_id": competency.id,
                "id": competency.code,
                "group": competency.group,
                "name": competency.description,
            }
            for competency in competencies
        ],
        "courses": [
            CourseOut(
                db_id=course.id,
                code=course.code,
                title=course.title,
                semester=course.semester,
                t=sorted(links_by_course.get(course.id, [])),
            )
            for course in courses
        ],
    }
