from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Competency, Course, Document, DocumentChunk, Evidence, EvaluationCriterion
from app.db.session import get_db
from app.schemas.api import EvidenceOut


router = APIRouter()


def _merge_duplicate_fragments(items: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for item in items:
        key = (item["period_id"], item["criterion_id"], item["_chunk_id"])
        existing = grouped.get(key)
        course_label = item["course_code"] or item["course_title"]
        if not existing:
            item["related_courses"] = [course_label] if course_label else []
            item["occurrence_count"] = 1
            grouped[key] = item
            continue

        existing["occurrence_count"] += 1
        if course_label and course_label not in existing["related_courses"]:
            existing["related_courses"].append(course_label)
        if item["confidence"] > existing["confidence"]:
            for field in [
                "id",
                "course_id",
                "course_code",
                "course_title",
                "semantic_score",
                "confidence",
                "verdict",
                "observation",
            ]:
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


@router.get("", response_model=list[EvidenceOut])
def list_evidence(
    period_id: str | None = None,
    criterion_id: str | None = None,
    course_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(Evidence)
    if period_id:
        query = query.filter(Evidence.period_id == period_id)
    if criterion_id:
        query = query.filter(Evidence.criterion_id == criterion_id)
    if course_id:
        query = query.filter(Evidence.course_id == course_id)

    settings = get_settings()
    from app.services.analysis import _score_to_percent
    
    rows = query.order_by(Evidence.confidence.desc()).limit(min(max(limit * 8, 100), 500)).all()
    payload = []
    for evidence in rows:
        criterion = db.get(EvaluationCriterion, evidence.criterion_id)
        competency = db.get(Competency, criterion.competency_id) if criterion else None
        course = db.get(Course, evidence.course_id)
        chunk = db.get(DocumentChunk, evidence.chunk_id)
        document_title = ""
        if chunk and chunk.version and chunk.version.document:
            document: Document = chunk.version.document
            document_title = document.title
            
        calibrated_confidence = _score_to_percent(evidence.confidence or 0.0, settings.evidence_threshold) / 100.0
            
        payload.append(
            {
                "id": evidence.id,
                "period_id": evidence.period_id,
                "_chunk_id": evidence.chunk_id,
                "course_id": evidence.course_id,
                "course_code": course.code if course else "",
                "course_title": course.title if course else "",
                "related_courses": [],
                "occurrence_count": 1,
                "competency_code": competency.code if competency else "",
                "competency_group": competency.group if competency else "",
                "criterion_id": evidence.criterion_id,
                "criterion_name": criterion.name if criterion else "",
                "document_title": document_title,
                "page": chunk.page if chunk else 0,
                "text": chunk.text if chunk else "",
                "semantic_score": evidence.semantic_score,
                "confidence": calibrated_confidence,
                "verdict": evidence.verdict,
                "observation": evidence.observation,
            }
        )
    if not course_id:
        payload = _merge_duplicate_fragments(payload)
    for item in payload:
        item.pop("_chunk_id", None)
    return payload[: min(limit, 100)]
