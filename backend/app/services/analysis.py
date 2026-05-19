from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AcademicPeriod,
    ChunkEmbedding,
    Competency,
    Course,
    CourseCompetency,
    Document,
    DocumentChunk,
    DocumentVersion,
    EvaluationCriterion,
    EvaluationResult,
    Evidence,
    Report,
)
from app.services.embeddings import EmbeddingService
from app.services.locks import sqlite_write_lock
from app.services.llm_comments import CellCommentInput, LLMCellCommentService
from app.services.progress import (
    finish_analysis_progress,
    start_analysis_progress,
    update_analysis_progress,
)
from app.services.scoring import (
    HybridEvidenceRanker,
    RankedChunk,
    expand_tokens,
    lexical_overlap,
    phrase_overlap,
    section_signal,
    tokenize,
)
from app.services.document_processing import process_document_version


def _score_to_percent(score: float, threshold: float = 0.22) -> int:
    """Convert an internal hybrid score into a dashboard percentage.

    Hybrid scores are conservative because they combine partial semantic, lexical,
    phrase and section signals. A raw 0.30 can be valid evidence, so the dashboard
    percentage is calibrated around the evidence threshold instead of shown 1:1.
    """

    score = max(0.0, min(1.0, score))
    threshold = max(0.05, min(0.6, threshold))

    if score < threshold:
        return round(25 + (score / threshold) * 34)
    if score < 0.55:
        return round(60 + ((score - threshold) / (0.55 - threshold)) * 24)
    if score < 0.80:
        return round(84 + ((score - 0.55) / 0.25) * 10)
    return round(94 + ((score - 0.80) / 0.20) * 4)


def _observation(course: Course, competency: Competency, score: int, ranked: RankedChunk) -> str:
    if score >= 75:
        level = "alta"
    elif score >= 55:
        level = "media"
    else:
        level = "baja"
    excerpt = ranked.chunk.text[:220].replace("\n", " ").strip()
    terms = ", ".join(ranked.matched_terms[:6]) if ranked.matched_terms else "sin terminos directos"
    return (
        f"Evidencia {level} para {course.title} respecto de {competency.code}. "
        f"Score hibrido {score}% "
        f"(semantico {ranked.semantic_score:.2f}, lexico {ranked.lexical_score:.2f}). "
        f"Terminos coincidentes: {terms}. Fragmento: {excerpt}"
    )


def _ranked_signal(ranked: RankedChunk) -> float:
    return (
        ranked.hybrid_score * 0.50
        + ranked.lexical_score * 0.22
        + ranked.semantic_score * 0.18
        + ranked.phrase_score * 0.07
        + ranked.section_score * 0.03
    )


def _weighted_topk_signal(ranked_chunks: list[RankedChunk]) -> float:
    if not ranked_chunks:
        return 0.0
    weights = [0.50, 0.24, 0.14, 0.08, 0.04]
    usable = ranked_chunks[: len(weights)]
    total_weight = sum(weights[: len(usable)])
    return sum(_ranked_signal(item) * weight for item, weight in zip(usable, weights, strict=False)) / total_weight


def _curricular_alignment(course: Course, criterion: EvaluationCriterion) -> float:
    course_tokens = expand_tokens(tokenize(f"{course.code} {course.title}"))
    criterion_tokens = expand_tokens(
        tokenize(f"{criterion.name} {criterion.description} {criterion.competency.description}")
    )
    if not course_tokens or not criterion_tokens:
        return 0.0
    course_to_criterion, _ = lexical_overlap(course_tokens, criterion_tokens)
    criterion_to_course, _ = lexical_overlap(criterion_tokens, course_tokens)
    return max(course_to_criterion, criterion_to_course)


def _stable_cell_tiebreaker(course_id: str, criterion_id: str) -> float:
    digest = hashlib.blake2b(f"{course_id}:{criterion_id}".encode("utf-8"), digest_size=2).digest()
    value = int.from_bytes(digest, "big") / 65535
    return (value - 0.5) * 0.035


def _cell_adjusted_score(
    base_score: float,
    course_ranked_chunks: list[RankedChunk],
    competency_ranked_chunks: list[RankedChunk],
    course: Course | None = None,
    criterion: EvaluationCriterion | None = None,
) -> float:
    """Add per-course variation without letting course names dominate the evidence."""

    course_signal = _weighted_topk_signal(course_ranked_chunks)
    competency_signal = _weighted_topk_signal(competency_ranked_chunks)
    alignment = _curricular_alignment(course, criterion) if course and criterion else 0.0
    tiebreaker = _stable_cell_tiebreaker(course.id, criterion.id) if course and criterion else 0.0

    # Keep the competency evidence as the anchor, but reward or penalize the cell
    # when the course-specific signal is meaningfully different.
    adjusted = base_score + (course_signal - competency_signal) * 0.42 + alignment * 0.08 + tiebreaker
    return max(0.0, min(1.0, adjusted))


def run_period_analysis(db: Session, period_id: str, embedding_device: str | None = None) -> dict:
    with sqlite_write_lock:
        try:
            return _run_period_analysis(db, period_id, embedding_device)
        except Exception as exc:
            finish_analysis_progress(
                period_id,
                "failed",
                "El analisis fallo antes de completarse.",
                str(exc),
            )
            raise


def _run_period_analysis(db: Session, period_id: str, embedding_device: str | None = None) -> dict:
    settings = get_settings()
    period = db.get(AcademicPeriod, period_id)
    if not period:
        raise ValueError(f"No existe el periodo {period_id}")

    period.status = "processing"
    db.query(EvaluationResult).filter(EvaluationResult.period_id == period_id).delete()
    db.query(Evidence).filter(Evidence.period_id == period_id).delete()
    db.commit()

    latest_versions = []
    documents = (
        db.query(Document)
        .filter(Document.period_id == period_id, Document.status != "deleted")
        .all()
    )
    for document in documents:
        if document.versions:
            latest_versions.append(sorted(document.versions, key=lambda item: item.version_number)[-1])

    embedding_service = EmbeddingService(device=embedding_device)
    version_ids = [version.id for version in latest_versions]
    start_analysis_progress(period_id, len(latest_versions), embedding_service.device or "auto")

    if version_ids:
        existing_embeddings = (
            db.query(DocumentChunk.version_id, ChunkEmbedding.model, ChunkEmbedding.dimensions)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .filter(DocumentChunk.version_id.in_(version_ids))
            .all()
        )
        embedding_meta_by_version: dict[str, set[tuple[str, int]]] = defaultdict(set)
        for version_id, model, dimensions in existing_embeddings:
            embedding_meta_by_version[version_id].add((model, dimensions))

        total_versions = max(len(latest_versions), 1)
        for index, version in enumerate(latest_versions, start=1):
            document = version.document
            base_progress = int(((index - 1) / total_versions) * 60)
            update_analysis_progress(
                period_id,
                step="checking_document",
                ui_step=0,
                progress=base_progress,
                current_document_id=document.id,
                current_document_title=document.title,
                current_index=index,
                total_documents=len(latest_versions),
                message=f"Verificando tesis {index}/{len(latest_versions)}: {document.title}",
            )
            metas = embedding_meta_by_version.get(version.id, set())
            if metas != {(embedding_service.model_name, embedding_service.dimensions)}:
                def _document_progress(step: str, progress: int, message: str) -> None:
                    overall = int(((index - 1) + progress / 100) / total_versions * 60)
                    ui_step = {
                        "extracting": 1,
                        "chunking": 2,
                        "embedding": 3,
                        "ready": 3,
                    }.get(step, 0)
                    update_analysis_progress(
                        period_id,
                        step=f"document_{step}",
                        ui_step=ui_step,
                        progress=overall,
                        current_document_id=document.id,
                        current_document_title=document.title,
                        current_index=index,
                        total_documents=len(latest_versions),
                        message=f"Tesis {index}/{len(latest_versions)} - {message}",
                    )

                process_document_version(
                    db,
                    version.id,
                    embedding_device=embedding_device,
                    progress_callback=_document_progress,
                )
            else:
                update_analysis_progress(
                    period_id,
                    step="document_cached",
                    ui_step=3,
                    progress=int((index / total_versions) * 60),
                    current_document_id=document.id,
                    current_document_title=document.title,
                    current_index=index,
                    total_documents=len(latest_versions),
                    message=f"Tesis {index}/{len(latest_versions)} ya tenia embeddings vigentes: {document.title}",
                )

    update_analysis_progress(
        period_id,
        step="loading_embeddings",
        ui_step=3,
        progress=65,
        current_document_id=None,
        current_document_title="",
        current_index=len(latest_versions),
        total_documents=len(latest_versions),
        message="Cargando embeddings del periodo para evaluar la matriz.",
    )
    chunks = (
        db.query(DocumentChunk, ChunkEmbedding)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .filter(
            DocumentChunk.version_id.in_(version_ids),
            ChunkEmbedding.model == embedding_service.model_name,
            ChunkEmbedding.dimensions == embedding_service.dimensions,
        )
        .all()
    )

    if not chunks:
        period.status = "empty" if not documents else "warning"
        period.updated_at = datetime.utcnow()
        db.commit()
        finish_analysis_progress(
            period_id,
            "completed",
            "No hay chunks procesados para este periodo.",
        )
        return {"evaluated_cells": 0, "average": 0, "evidence": 0}

    ranker = HybridEvidenceRanker(embedding_service)
    criteria = db.query(EvaluationCriterion).all()
    course_links = db.query(CourseCompetency).all()
    links_by_competency: dict[str, list[CourseCompetency]] = defaultdict(list)
    for link in course_links:
        links_by_competency[link.competency_id].append(link)

    evidence_count = 0
    result_scores = []
    total_criteria = max(len(criteria), 1)
    for criterion_index, criterion in enumerate(criteria, start=1):
        update_analysis_progress(
            period_id,
            step="analysis_matrix",
            ui_step=4,
            progress=70 + int(((criterion_index - 1) / total_criteria) * 25),
            current_document_id=None,
            current_document_title="",
            current_index=len(latest_versions),
            total_documents=len(latest_versions),
            message=f"Evaluando competencia {criterion_index}/{len(criteria)}: {criterion.competency.code}",
        )
        competency_query_text = "\n".join(
            [
                criterion.name,
                criterion.description,
                criterion.competency.description,
            ]
        )
        competency_query_vector = embedding_service.embed(competency_query_text)
        competency_ranked_chunks = ranker.rank(
            competency_query_text,
            competency_query_vector,
            chunks,
        )[: settings.top_k_evidence]

        for link in links_by_competency.get(criterion.competency_id, []):
            course_query_text = "\n".join(
                [
                    criterion.description,
                    criterion.competency.description,
                    link.course.title,
                    link.course.code,
                ]
            )
            course_query_vector = embedding_service.embed(course_query_text)
            course_ranked_chunks = ranker.rank(
                course_query_text,
                course_query_vector,
                chunks,
            )[: settings.top_k_evidence]
            threshold = max(criterion.threshold, settings.evidence_threshold)
            best_competency = competency_ranked_chunks[0]
            adjusted_score = _cell_adjusted_score(
                best_competency.hybrid_score,
                course_ranked_chunks,
                competency_ranked_chunks,
                link.course,
                criterion,
            )

            valid_chunks_by_id = {
                item.chunk.id: item
                for item in [*competency_ranked_chunks, *course_ranked_chunks]
                if item.hybrid_score >= threshold
            }
            best_course = course_ranked_chunks[0] if course_ranked_chunks else None
            if best_course and best_course.chunk.id not in valid_chunks_by_id:
                # Keep at least one course-specific candidate so the cell detail
                # does not always fall back to the same competency-level fragment.
                valid_chunks_by_id[best_course.chunk.id] = best_course
            valid_chunks = sorted(
                valid_chunks_by_id.values(),
                key=lambda item: item.hybrid_score,
                reverse=True,
            )[: settings.top_k_evidence]
            if not valid_chunks:
                valid_chunks = [best_competency]

            best_ranked = valid_chunks[0]
            percent = _score_to_percent(adjusted_score, threshold)
            confidence = max(0.0, min(1.0, adjusted_score))
            observation = _observation(link.course, criterion.competency, percent, best_ranked)

            db.add(
                EvaluationResult(
                    period_id=period_id,
                    document_id=None,
                    criterion_id=criterion.id,
                    course_id=link.course_id,
                    score=percent,
                    confidence=confidence,
                    status="ready",
                    summary=observation,
                )
            )
            result_scores.append(percent)

            for ranked in valid_chunks:
                chunk_score = ranked.hybrid_score
                db.add(
                    Evidence(
                        period_id=period_id,
                        chunk_id=ranked.chunk.id,
                        criterion_id=criterion.id,
                        course_id=link.course_id,
                        semantic_score=chunk_score,
                        confidence=max(0.0, min(1.0, chunk_score)),
                        verdict="supporting" if chunk_score >= threshold else "candidate",
                        observation=_observation(
                            link.course,
                            criterion.competency,
                            _score_to_percent(chunk_score, threshold),
                            ranked,
                        ),
                    )
                )
                evidence_count += 1

    average = round(sum(result_scores) / len(result_scores)) if result_scores else 0
    low = len([score for score in result_scores if score < 55])
    period.status = "ready"
    period.analyzed_at = datetime.utcnow()
    period.updated_at = datetime.utcnow()
    db.add(
        Report(
            period_id=period_id,
            report_type="dashboard",
            payload={
                "average": average,
                "evaluated_cells": len(result_scores),
                "evidence": evidence_count,
                "gaps": low,
            },
        )
    )
    db.commit()
    finish_analysis_progress(
        period_id,
        "completed",
        f"Analisis listo: {len(result_scores)} celdas evaluadas y {evidence_count} evidencias.",
    )
    return {
        "evaluated_cells": len(result_scores),
        "average": average,
        "evidence": evidence_count,
        "gaps": low,
    }


def _score_level(score: int | None) -> str:
    if score is None:
        return "pendiente"
    if score >= 75:
        return "alta"
    if score >= 55:
        return "media"
    return "baja"


def _trim_text(text: str, limit: int = 460) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1].rstrip()}..."


@dataclass(frozen=True)
class CompetencyEvidenceSummary:
    comment: str
    context: str
    reviewed_documents: int
    evidence_documents: int
    evidence_count: int


_COMMENT_STOPWORDS = {
    "ademas",
    "analisis",
    "como",
    "competencia",
    "con",
    "criterio",
    "desde",
    "documento",
    "evidencia",
    "fueron",
    "hacia",
    "para",
    "pero",
    "proyecto",
    "realizo",
    "resultados",
    "sistema",
    "sobre",
    "tesis",
    "trabajo",
    "traves",
    "una",
    "usar",
    "utiliza",
}


def _top_comment_terms(texts: list[str], limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for text in texts:
        for token in tokenize(text):
            if len(token) < 5 or token in _COMMENT_STOPWORDS:
                continue
            counts[token] += 1
    return [term for term, _count in counts.most_common(limit)]


def _competency_evidence_summary(
    db: Session,
    period_id: str,
    course: Course,
    competency: Competency,
    criterion: EvaluationCriterion,
) -> CompetencyEvidenceSummary:
    settings = get_settings()
    threshold = max(criterion.threshold, settings.evidence_threshold)
    reviewed_documents = (
        db.query(Document)
        .filter(Document.period_id == period_id, Document.status != "deleted")
        .count()
    )
    rows = (
        db.query(Evidence, DocumentChunk, Document)
        .join(DocumentChunk, Evidence.chunk_id == DocumentChunk.id)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .filter(
            Evidence.period_id == period_id,
            Evidence.criterion_id == criterion.id,
            Document.status != "deleted",
        )
        .order_by(Evidence.confidence.desc(), Evidence.semantic_score.desc())
        .limit(180)
        .all()
    )

    seen_chunks: set[str] = set()
    by_document: dict[str, dict] = {}
    representative_texts: list[str] = []
    for evidence, chunk, document in rows:
        if chunk.id in seen_chunks:
            continue
        seen_chunks.add(chunk.id)
        item = by_document.setdefault(
            document.id,
            {
                "title": document.title,
                "max_confidence": 0.0,
                "pages": set(),
                "snippets": [],
            },
        )
        item["max_confidence"] = max(item["max_confidence"], evidence.confidence or 0.0)
        if chunk.page:
            item["pages"].add(chunk.page)
        if len(item["snippets"]) < 2:
            snippet = _trim_text(chunk.text, 230)
            item["snippets"].append(snippet)
            representative_texts.append(snippet)

    evidence_documents = len(by_document)
    evidence_count = len(seen_chunks)
    if not evidence_documents:
        comment = (
            f"El sistema reviso {reviewed_documents} tesis del periodo y no encontro evidencia textual "
            f"suficiente para resumir la competencia {competency.code}. En este estado, la celda debe "
            "interpretarse como una alerta de cobertura: no hay respaldo agregado confiable para el "
            f"cruce con {course.code or course.title}."
        )
        context = "- No hay documentos con evidencia recuperada para esta competencia."
        return CompetencyEvidenceSummary(comment, context, reviewed_documents, 0, 0)

    top_documents = sorted(
        by_document.values(),
        key=lambda item: item["max_confidence"],
        reverse=True,
    )
    document_bits = [
        f"{_trim_text(item['title'], 72)} ({_score_to_percent(item['max_confidence'], threshold)}%)"
        for item in top_documents[:5]
    ]
    terms = _top_comment_terms(representative_texts)
    topic_text = ", ".join(terms[:6]) if terms else "los temas tecnicos recuperados"
    coverage = (
        f"{evidence_documents} de {reviewed_documents} tesis"
        if reviewed_documents
        else f"{evidence_documents} tesis"
    )
    comment = (
        f"Para la competencia {competency.code}, el sistema reviso {reviewed_documents} tesis del periodo "
        f"y encontro evidencia asociada en {coverage}, con {evidence_count} fragmentos unicos considerados. "
        f"Los indicios mas fuertes aparecen en {', '.join(document_bits)} en escala calibrada. "
        f"En conjunto, los fragmentos se concentran en {topic_text}, por lo que el resultado resume una "
        "tendencia agregada del grupo y no una sola memoria aislada. "
        f"Al leerlo junto al cruce {course.code or course.title} - {competency.code}, conviene validar si la "
        "evidencia distribuida realmente cubre el alcance completo de la competencia tributada."
    )
    context_lines = [
        f"- Documentos principales: {', '.join(document_bits)}",
        f"- Temas frecuentes: {topic_text}",
    ]
    for item in top_documents[:4]:
        pages = sorted(item["pages"])
        page_text = f"paginas {', '.join(str(page) for page in pages[:3])}" if pages else "sin pagina"
        if item["snippets"]:
            context_lines.append(
                f"- {_trim_text(item['title'], 72)} ({page_text}): {_trim_text(item['snippets'][0], 260)}"
            )

    return CompetencyEvidenceSummary(
        comment=_trim_text(comment, 1350),
        context="\n".join(context_lines),
        reviewed_documents=reviewed_documents,
        evidence_documents=evidence_documents,
        evidence_count=evidence_count,
    )


def _cell_action(score: int | None, confidence: float | None, has_evidence: bool) -> str:
    if score is None or not has_evidence:
        return (
            "Revisar manualmente la celda y pedir evidencias explicitas en futuras memorias; "
            "el sistema no encontro fragmentos suficientes para justificar este cruce."
        )
    if score >= 75 and (confidence or 0) >= 0.50:
        return (
            "Mantener la tributacion y usar los fragmentos recuperados como respaldo trazable "
            "en el informe curricular."
        )
    if score >= 55:
        return (
            "Mantener la celda en observacion y solicitar que las memorias expliciten mejor "
            "la relacion entre el trabajo realizado, el curso y la competencia."
        )
    return (
        "Priorizar esta celda en revision academica: conviene definir evidencia minima, "
        "rubrica asociada o ejemplos esperados para futuras tesis."
    )


def _cell_evidence_chunks(
    db: Session,
    period_id: str,
    course_id: str,
    criterion_id: str,
) -> list[tuple[DocumentChunk, Evidence]]:
    return (
        db.query(DocumentChunk, Evidence)
        .join(Evidence, Evidence.chunk_id == DocumentChunk.id)
        .filter(
            Evidence.period_id == period_id,
            Evidence.course_id == course_id,
            Evidence.criterion_id == criterion_id,
        )
        .all()
    )


def _best_cell_ranked_chunk(
    db: Session,
    period_id: str,
    course: Course,
    competency: Competency,
    criterion: EvaluationCriterion,
) -> tuple[DocumentChunk, float] | None:
    chunks = _cell_evidence_chunks(db, period_id, course.id, criterion.id)
    if not chunks:
        return None

    query_text = "\n".join(
        [
            f"Curso {course.code}: {course.title}",
            f"Competencia {competency.code}: {competency.group}",
            competency.description,
            criterion.name,
            criterion.description,
        ]
    )
    query_tokens = expand_tokens(tokenize(query_text))
    ranked: list[tuple[float, DocumentChunk]] = []
    for chunk, evidence in chunks:
        chunk_tokens = tokenize(chunk.text)
        lexical, _matched = lexical_overlap(query_tokens, chunk_tokens)
        phrase = phrase_overlap(query_tokens, chunk_tokens)
        section = section_signal(chunk_tokens)
        score = evidence.confidence * 0.25 + lexical * 0.55 + phrase * 0.12 + section * 0.08
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return None

    top_score = ranked[0][0]
    relevant = [item for item in ranked if item[0] >= max(top_score * 0.82, top_score - 0.08)]
    relevant = relevant[: min(len(relevant), 5)]
    selected_index = (course.sort_order * 7 + competency.sort_order * 11) % len(relevant)
    selected = relevant[selected_index]
    return (selected[1], selected[0])


def build_cell_detail(
    db: Session,
    period_id: str,
    course_id: str,
    competency_id: str,
) -> dict:
    period = db.get(AcademicPeriod, period_id)
    course = db.get(Course, course_id)
    competency = db.get(Competency, competency_id)
    if not period or not course or not competency:
        raise ValueError("Periodo, curso o competencia no encontrado.")

    criterion = (
        db.query(EvaluationCriterion)
        .filter(EvaluationCriterion.competency_id == competency_id)
        .order_by(EvaluationCriterion.name)
        .first()
    )
    if not criterion:
        raise ValueError("La competencia no tiene criterio de evaluacion asociado.")

    result = (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.period_id == period_id,
            EvaluationResult.course_id == course_id,
            EvaluationResult.criterion_id == criterion.id,
        )
        .first()
    )
    saved_evidence = (
        db.query(Evidence)
        .filter(
            Evidence.period_id == period_id,
            Evidence.course_id == course_id,
            Evidence.criterion_id == criterion.id,
        )
        .order_by(Evidence.confidence.desc(), Evidence.semantic_score.desc())
        .first()
    )

    score = round(result.score) if result else None
    confidence = result.confidence if result else None
    level = _score_level(score)

    evidence_text = ""
    evidence_origin = "Sin evidencia textual suficiente"
    evidence_page: int | None = None
    evidence_confidence: float | None = None
    cell_chunk = _best_cell_ranked_chunk(db, period_id, course, competency, criterion)
    if cell_chunk:
        chunk, chunk_score = cell_chunk
        evidence_text = _trim_text(chunk.text)
        evidence_page = chunk.page
        evidence_confidence = chunk_score
        if chunk.version and chunk.version.document:
            evidence_origin = chunk.version.document.title
    elif saved_evidence:
        chunk = db.get(DocumentChunk, saved_evidence.chunk_id)
        if chunk:
            evidence_text = _trim_text(chunk.text)
            evidence_page = chunk.page
            evidence_confidence = saved_evidence.confidence
            if chunk.version and chunk.version.document:
                evidence_origin = chunk.version.document.title

    if evidence_text:
        justification = (
            f"El analisis IA clasifica este cruce con evidencia {level} ({score}%). "
            f"Para justificarlo comparo la competencia {competency.code}, el curso {course.code} "
            f"y el criterio academico mediante embeddings y ranking hibrido. "
            f"La evidencia principal proviene de un fragmento con confianza "
            f"{(evidence_confidence or confidence or 0):.2f}; por eso la conclusion queda ligada "
            f"a un documento y pagina especificos, no a una inferencia aislada."
        )
    elif result:
        justification = (
            f"El analisis IA genero un resultado {level} ({score}%), pero no encontro un fragmento "
            "suficientemente fuerte para presentarlo como evidencia textual principal. "
            "La celda debe revisarse manualmente antes de usarla como respaldo academico."
        )
    else:
        justification = (
            "Aun no hay resultado IA para esta celda. Ejecuta Analizar con API despues de que "
            "las tesis terminen su procesamiento para generar evidencia trazable."
        )
    suggested_action = _cell_action(score, confidence, bool(evidence_text))
    general_summary = _competency_evidence_summary(db, period_id, course, competency, criterion)
    general_comment = general_summary.comment
    source = "ai-rag-evidence"

    llm_comment = LLMCellCommentService().generate(
        CellCommentInput(
            course_code=course.code,
            course_title=course.title,
            competency_code=competency.code,
            competency_group=competency.group,
            competency_description=competency.description,
            criterion_description=criterion.description,
            score=score,
            confidence=confidence,
            evidence_text=evidence_text
            or "No hay fragmento textual suficientemente confiable para esta celda.",
            evidence_origin=evidence_origin,
            evidence_page=evidence_page,
            general_context=general_summary.context,
            reviewed_documents=general_summary.reviewed_documents,
            evidence_documents=general_summary.evidence_documents,
            evidence_count=general_summary.evidence_count,
        )
    )
    if llm_comment:
        justification = llm_comment.justification
        if llm_comment.general_comment:
            general_comment = llm_comment.general_comment
        suggested_action = llm_comment.suggested_action
        source = llm_comment.source

    return {
        "period_id": period_id,
        "course_id": course.id,
        "course_code": course.code,
        "course_title": course.title,
        "competency_id": competency.id,
        "competency_code": competency.code,
        "competency_group": competency.group,
        "competency_description": competency.description,
        "score": score,
        "confidence": confidence,
        "justification": justification,
        "general_comment": general_comment,
        "general_document_count": general_summary.reviewed_documents,
        "general_evidence_document_count": general_summary.evidence_documents,
        "general_evidence_count": general_summary.evidence_count,
        "evidence_text": evidence_text
        or "No hay fragmento textual suficientemente confiable para esta celda.",
        "evidence_origin": evidence_origin,
        "evidence_page": evidence_page,
        "suggested_action": suggested_action,
        "source": source,
    }


def build_period_analysis(db: Session, period_id: str) -> dict:
    period = db.get(AcademicPeriod, period_id)
    if not period:
        raise ValueError(f"No existe el periodo {period_id}")

    results = db.query(EvaluationResult).filter(EvaluationResult.period_id == period_id).all()
    result_by_cell = {(result.course_id, result.criterion_id): result for result in results}

    evidence_counts: dict[tuple[str, str], int] = defaultdict(int)
    for evidence in db.query(Evidence).filter(Evidence.period_id == period_id).all():
        evidence_counts[(evidence.course_id, evidence.criterion_id)] += 1

    total_docs = db.query(Document).filter(Document.period_id == period_id, Document.status != "deleted").count()
    evidence_query = (
        db.query(Evidence.criterion_id, DocumentVersion.document_id)
        .join(DocumentChunk, Evidence.chunk_id == DocumentChunk.id)
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .filter(
            Evidence.period_id == period_id,
            Document.status != "deleted"
        )
        .distinct()
        .all()
    )
    docs_by_criterion = defaultdict(int)
    for criterion_id, doc_id in evidence_query:
        docs_by_criterion[criterion_id] += 1

    cells = []
    links = db.query(CourseCompetency).join(Course).join(Competency).all()
    criteria_evaluated = set()
    for link in links:
        criterion = link.competency.criteria[0] if link.competency.criteria else None
        if not criterion:
            continue
        criteria_evaluated.add(criterion.id)
        result = result_by_cell.get((link.course_id, criterion.id))
        cells.append(
            {
                "course_id": link.course_id,
                "course_code": link.course.code,
                "course_title": link.course.title,
                "competency_id": link.competency_id,
                "competency_code": link.competency.code,
                "score": round(result.score) if result else None,
                "confidence": result.confidence if result else None,
                "status": "ready" if result else "pending",
                "evidence_count": evidence_counts.get((link.course_id, criterion.id), 0),
            }
        )

    if criteria_evaluated and total_docs > 0:
        sum_traceability = sum(
            (docs_by_criterion[crit_id] / total_docs) * 100
            for crit_id in criteria_evaluated
        )
        avg_traceability = round(sum_traceability / len(criteria_evaluated))
    else:
        avg_traceability = 0

    scores = [cell["score"] for cell in cells if cell["score"] is not None]
    metrics = {
        "average": round(sum(scores) / len(scores)) if scores else 0,
        "traceability": avg_traceability,
        "evaluated_cells": len(scores),
        "gaps": len([score for score in scores if score < 55]),
        "high": len([score for score in scores if score >= 75]),
        "medium": len([score for score in scores if 55 <= score < 75]),
        "low": len([score for score in scores if score < 55]),
    }

    return {
        "period_id": period_id,
        "status": period.status,
        "generated_at": period.analyzed_at.isoformat() if period.analyzed_at else None,
        "cells": cells,
        "metrics": metrics,
    }
