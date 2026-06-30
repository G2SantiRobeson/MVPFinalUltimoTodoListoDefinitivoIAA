from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AcademicPeriod,
    Base,
    Competency,
    Course,
    CourseCompetency,
    Curriculum,
    EvaluationCriterion,
    EvaluationResult,
    Evidence,
    Program,
)
from app.services.analysis import build_period_analysis, review_evidence_score


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def _curriculum_cell(
    db: Session,
    program_name: str,
    curriculum_name: str,
    course_code: str,
    competency_code: str,
) -> tuple[Curriculum, Course, Competency, EvaluationCriterion]:
    program = Program(name=program_name)
    db.add(program)
    db.flush()
    curriculum = Curriculum(
        program_id=program.id,
        year=2026,
        version=curriculum_name.upper(),
        display_name=curriculum_name,
    )
    db.add(curriculum)
    db.flush()
    course = Course(
        curriculum_id=curriculum.id,
        code=course_code,
        title=f"Curso {course_code}",
        sort_order=1,
    )
    competency = Competency(
        curriculum_id=curriculum.id,
        code=competency_code,
        group="TIC",
        description=f"Competencia {competency_code}",
        sort_order=1,
    )
    db.add_all([course, competency])
    db.flush()
    criterion = EvaluationCriterion(
        competency_id=competency.id,
        name=f"Evidencia para {competency_code}",
        description=competency.description,
        threshold=0.22,
    )
    db.add(criterion)
    db.flush()
    db.add(CourseCompetency(course_id=course.id, competency_id=competency.id))
    db.flush()
    return curriculum, course, competency, criterion


def test_manual_evidence_review_recalculates_cell_result():
    """La opinion del evaluador debe cambiar el porcentaje visible de la celda."""
    db = _session()
    curriculum, course, _competency, criterion = _curriculum_cell(
        db,
        "Ingenieria Civil Electrica",
        "PE 2026 Electrica",
        "IEL101",
        "TIC1",
    )
    period = AcademicPeriod(name="2026-1", curriculum_id=curriculum.id, status="ready")
    db.add(period)
    db.flush()
    evidence = Evidence(
        period_id=period.id,
        chunk_id="chunk-1",
        criterion_id=criterion.id,
        course_id=course.id,
        semantic_score=0.30,
        confidence=0.30,
        verdict="supporting",
    )
    db.add(evidence)
    db.flush()

    # Arrange
    db.add(
        EvaluationResult(
            period_id=period.id,
            document_id=None,
            criterion_id=criterion.id,
            course_id=course.id,
            score=68,
            confidence=0.68,
            status="ready",
        )
    )
    db.commit()

    # Act
    review_evidence_score(
        db,
        evidence.id,
        manual_score=42,
        manual_observation="No cubre alcance.",
        actor_id=None,
    )

    # Assert
    result = (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.period_id == period.id,
            EvaluationResult.course_id == course.id,
            EvaluationResult.criterion_id == criterion.id,
        )
        .one()
    )
    assert result.score == 42
    assert result.status == "reviewed"


def test_false_positive_review_is_excluded_from_cell_result():
    """Una evidencia rechazada no debe bajar el promedio: deja de contar."""
    db = _session()
    curriculum, course, _competency, criterion = _curriculum_cell(
        db,
        "Ingenieria Civil Electrica",
        "PE 2026 Electrica",
        "IEL101",
        "TIC1",
    )
    period = AcademicPeriod(name="2026-1", curriculum_id=curriculum.id, status="ready")
    db.add(period)
    db.flush()
    kept_evidence = Evidence(
        period_id=period.id,
        chunk_id="chunk-active",
        criterion_id=criterion.id,
        course_id=course.id,
        semantic_score=0.42,
        confidence=0.42,
        verdict="supporting",
        manual_score=80,
        manual_verdict="supporting",
    )
    rejected_evidence = Evidence(
        period_id=period.id,
        chunk_id="chunk-rejected",
        criterion_id=criterion.id,
        course_id=course.id,
        semantic_score=0.35,
        confidence=0.35,
        verdict="supporting",
    )
    db.add_all([kept_evidence, rejected_evidence])
    db.flush()
    db.add(
        EvaluationResult(
            period_id=period.id,
            document_id=None,
            criterion_id=criterion.id,
            course_id=course.id,
            score=90,
            confidence=0.90,
            status="ready",
        )
    )
    db.commit()

    review_evidence_score(
        db,
        rejected_evidence.id,
        manual_score=0,
        manual_observation="",
        actor_id=None,
        manual_verdict="false_positive",
    )

    result = (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.period_id == period.id,
            EvaluationResult.course_id == course.id,
            EvaluationResult.criterion_id == criterion.id,
        )
        .one()
    )
    db.refresh(rejected_evidence)

    assert rejected_evidence.verdict == "false_positive"
    assert rejected_evidence.manual_verdict == "false_positive"
    assert result.score == 80
    assert "falso positivo" in result.summary

    analysis = build_period_analysis(db, period.id)
    assert analysis["cells"][0]["evidence_count"] == 1


def test_period_analysis_uses_only_the_period_curriculum():
    """Un periodo de una carrera no debe mostrar celdas de otra matriz cargada."""
    db = _session()
    electrical, electrical_course, _electrical_competency, electrical_criterion = _curriculum_cell(
        db,
        "Ingenieria Civil Electrica",
        "PE 2026 Electrica",
        "IEL101",
        "TIC1",
    )
    _industrial, industrial_course, _industrial_competency, industrial_criterion = _curriculum_cell(
        db,
        "Ingenieria Civil Industrial",
        "PE 2026 Industrial",
        "IND101",
        "TIC1",
    )
    period = AcademicPeriod(name="2026-1", curriculum_id=electrical.id, status="ready")
    db.add(period)
    db.flush()
    db.add_all(
        [
            EvaluationResult(
                period_id=period.id,
                document_id=None,
                criterion_id=electrical_criterion.id,
                course_id=electrical_course.id,
                score=80,
                confidence=0.80,
                status="ready",
            ),
            EvaluationResult(
                period_id=period.id,
                document_id=None,
                criterion_id=industrial_criterion.id,
                course_id=industrial_course.id,
                score=10,
                confidence=0.10,
                status="ready",
            ),
        ]
    )
    db.commit()

    # Arrange
    expected_course_ids = {electrical_course.id}

    # Act
    analysis = build_period_analysis(db, period.id)

    # Assert
    returned_course_ids = {cell["course_id"] for cell in analysis["cells"]}
    assert returned_course_ids == expected_course_ids
