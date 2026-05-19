from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Competency, Course, CourseCompetency, Curriculum
from app.db.session import get_db
from app.schemas.api import CourseOut, MatrixOut


router = APIRouter()


@router.get("/current/matrix", response_model=MatrixOut)
def current_matrix(db: Session = Depends(get_db)) -> dict:
    curriculum = db.query(Curriculum).order_by(Curriculum.year.desc()).first()
    if not curriculum:
        raise HTTPException(status_code=404, detail="No existe una malla cargada.")

    competencies = (
        db.query(Competency)
        .filter(Competency.curriculum_id == curriculum.id)
        .order_by(Competency.sort_order)
        .all()
    )
    competency_index = {competency.id: index for index, competency in enumerate(competencies)}
    links = db.query(CourseCompetency).all()
    links_by_course: dict[str, list[int]] = {}
    for link in links:
        if link.competency_id in competency_index:
            links_by_course.setdefault(link.course_id, []).append(competency_index[link.competency_id])

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
