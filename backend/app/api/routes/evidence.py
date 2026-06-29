from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_roles
from app.db.models import (
    Competency,
    Course,
    Document,
    DocumentChunk,
    Evidence,
    EvaluationCriterion,
    User,
)
from app.db.session import get_db
from app.schemas.api import EvidenceOut, EvidenceReviewIn
from app.services.analysis import review_evidence_score


router = APIRouter()


def _merge_duplicate_fragments(items: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for item in items:
        key = (item["period_id"], item["criterion_id"], item["_chunk_id"])
        existing = grouped.get(key)
        course_label = item["course_code"] or item["course_title"]
        related_cell = {
            "course_id": item["course_id"],
            "course_code": item["course_code"],
            "course_title": item["course_title"],
        }
        if not existing:
            item["related_courses"] = [course_label] if course_label else []
            item["related_cells"] = [related_cell]
            item["occurrence_count"] = 1
            grouped[key] = item
            continue

        existing["occurrence_count"] += 1
        if course_label and course_label not in existing["related_courses"]:
            existing["related_courses"].append(course_label)
        if not any(cell["course_id"] == item["course_id"] for cell in existing["related_cells"]):
            existing["related_cells"].append(related_cell)
        if item["confidence"] > existing["confidence"]:
            for field in [
                "id",
                "course_id",
                "course_code",
                "course_title",
                "semantic_score",
                "confidence",
                "manual_score",
                "effective_score",
                "verdict",
                "observation",
                "manual_observation",
                "reviewed_at",
            ]:
                if field in item:
                    existing[field] = item[field]

    merged = sorted(grouped.values(), key=lambda item: item["confidence"], reverse=True)
    for item in merged:
        if item["occurrence_count"] <= 1:
            continue
        document_title = item["document_title"]
        related = ", ".join(item["related_courses"][:6])
        suffix = "..." if len(item["related_courses"]) > 6 else ""
        item["course_code"] = "Evidencia"
        item["course_title"] = document_title
        item["document_title"] = f"{item['occurrence_count']} cruces asociados: {related}{suffix}"
    return merged


def _evidence_payload(db: Session, evidence: Evidence) -> dict:
    settings = get_settings()
    from app.services.analysis import _score_to_percent

    criterion = db.get(EvaluationCriterion, evidence.criterion_id)
    competency = db.get(Competency, criterion.competency_id) if criterion else None
    course = db.get(Course, evidence.course_id)
    chunk = db.get(DocumentChunk, evidence.chunk_id)
    document_title = ""
    if chunk and chunk.version and chunk.version.document:
        document: Document = chunk.version.document
        document_title = document.title

    effective_score = (
        round(evidence.manual_score)
        if evidence.manual_score is not None
        else _score_to_percent(evidence.confidence or 0.0, settings.evidence_threshold)
    )

    return {
        "id": evidence.id,
        "period_id": evidence.period_id,
        "_chunk_id": evidence.chunk_id,
        "course_id": evidence.course_id,
        "course_code": course.code if course else "",
        "course_title": course.title if course else "",
        "related_courses": [],
        "related_cells": [],
        "occurrence_count": 1,
        "competency_code": competency.code if competency else "",
        "competency_group": competency.group if competency else "",
        "criterion_id": evidence.criterion_id,
        "criterion_name": criterion.name if criterion else "",
        "document_title": document_title,
        "source_document_title": document_title,
        "page": chunk.page if chunk else 0,
        "text": chunk.text if chunk else "",
        "semantic_score": evidence.semantic_score,
        "confidence": effective_score / 100.0,
        "manual_score": round(evidence.manual_score) if evidence.manual_score is not None else None,
        "effective_score": effective_score,
        "verdict": evidence.verdict,
        "observation": evidence.observation,
        "manual_observation": evidence.manual_observation or "",
        "reviewed_at": evidence.reviewed_at.isoformat() if evidence.reviewed_at else None,
    }


@router.get("", response_model=list[EvidenceOut])
def list_evidence(
    period_id: str | None = None,
    criterion_id: str | None = None,
    competency_code: str | None = None,
    course_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(Evidence)
    if period_id:
        query = query.filter(Evidence.period_id == period_id)
    if criterion_id:
        query = query.filter(Evidence.criterion_id == criterion_id)
    if competency_code:
        query = (
            query.join(EvaluationCriterion, Evidence.criterion_id == EvaluationCriterion.id)
            .join(Competency, EvaluationCriterion.competency_id == Competency.id)
            .filter(Competency.code == competency_code)
        )
    if course_id:
        query = query.filter(Evidence.course_id == course_id)

    rows = query.order_by(Evidence.confidence.desc()).limit(min(max(limit * 8, 100), 500)).all()
    payload = [_evidence_payload(db, evidence) for evidence in rows]
    if not course_id:
        payload = _merge_duplicate_fragments(payload)
    for item in payload:
        item.pop("_chunk_id", None)
    return payload[: min(limit, 100)]


@router.patch("/{evidence_id}", response_model=EvidenceOut)
def update_evidence_review(
    evidence_id: str,
    payload: EvidenceReviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("evaluator", "academic_admin", "technical_admin")),
) -> dict:
    try:
        evidence = review_evidence_score(
            db,
            evidence_id=evidence_id,
            manual_score=payload.manual_score,
            manual_observation=payload.manual_observation,
            actor_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    item = _evidence_payload(db, evidence)
    item.pop("_chunk_id", None)
    return item
