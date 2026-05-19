"""KPI: Recall de detección de evidencia.

Mide la capacidad del pipeline de recuperación (embeddings + ranking híbrido)
para encontrar fragmentos de evidencia relevante.

Estrategia: *Synthetic Evidence Injection* (needle-in-a-haystack)
  1. Genera fragmentos sintéticos que sabemos son evidencia relevante para
     cada criterio de evaluación.
  2. Los mezcla con los chunks reales de un período ya procesado.
  3. Ejecuta el ranking híbrido y mide cuántos sintéticos aparecen en el top-K.
  4. Recall = sintéticos recuperados / total sintéticos inyectados.

Uso:
    python scripts/recall_kpi.py --period "2025-1" --top-k 5 --synthetic-per-criterion 3
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the backend package is importable when running as a script
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure the console can handle UTF-8 (avoids cp1252 errors on Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AcademicPeriod,
    ChunkEmbedding,
    DocumentChunk,
    EvaluationCriterion,
)
from app.db.session import SessionLocal
from app.services.embeddings import EmbeddingService
from app.services.scoring import HybridEvidenceRanker


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SyntheticFragment:
    """A synthetic evidence fragment with a known criterion association."""
    criterion_id: str
    competency_code: str
    criterion_name: str
    text: str
    tag: str  # unique identifier so we can track recovery


@dataclass
class CriterionRecallResult:
    criterion_id: str
    competency_code: str
    criterion_name: str
    injected: int
    recovered: int
    recall: float
    recovered_ranks: list[int] = field(default_factory=list)


@dataclass
class RecallReport:
    period_name: str
    top_k: int
    synthetic_per_criterion: int
    total_criteria: int
    total_real_chunks: int
    total_injected: int
    total_recovered: int
    global_recall: float
    baseline: float
    target: float
    status: str  # "CUMPLE OBJETIVO" | "SOBRE LINEA BASE" | "BAJO LINEA BASE"
    criteria_results: list[CriterionRecallResult] = field(default_factory=list)
    generated_at: str = ""
    generation_method: str = ""


# ── Synthetic fragment generation ─────────────────────────────────────────

_PARAPHRASE_TEMPLATES = [
    (
        "En el contexto del proyecto de titulo, se abordaron los aspectos relacionados "
        "con {description}. Los resultados obtenidos permiten evidenciar que los "
        "objetivos planteados fueron alcanzados, considerando {criterion_name} como "
        "eje central del trabajo realizado."
    ),
    (
        "La metodologia utilizada considero {criterion_name} como parte fundamental "
        "del desarrollo. En particular, se implementaron actividades orientadas a "
        "{description}, lo que permitio validar las competencias asociadas al perfil "
        "de egreso en el ambito de {competency_description}."
    ),
    (
        "El capitulo de resultados presenta evidencia directa respecto de "
        "{criterion_name}. Durante la ejecucion del proyecto, el estudiante demostro "
        "capacidades en {description}, alineadas con {competency_description}. "
        "Los artefactos generados respaldan el cumplimiento del criterio evaluado."
    ),
    (
        "Se observa que el trabajo desarrollado tributa directamente a "
        "{competency_description} a traves de {criterion_name}. La documentacion "
        "tecnica producida evidencia {description}, con trazabilidad entre las "
        "actividades realizadas y los resultados de aprendizaje esperados."
    ),
    (
        "El analisis realizado demuestra competencia en {criterion_name}, "
        "particularmente en lo que respecta a {description}. Esto se evidencia "
        "mediante los entregables del proyecto que cubren {competency_description}, "
        "proporcionando respaldo verificable para la evaluacion del perfil de egreso."
    ),
]


def _generate_local_synthetics(
    criteria: list[EvaluationCriterion],
    per_criterion: int,
) -> list[SyntheticFragment]:
    """Generate synthetic fragments using local paraphrase templates.

    This is the fallback when the LLM is not available.  The templates
    are deterministic but varied enough to test retrieval.
    """
    fragments: list[SyntheticFragment] = []
    for criterion in criteria:
        description = criterion.description[:200]
        competency_description = criterion.competency.description[:200]
        competency_code = criterion.competency.code

        for i in range(per_criterion):
            template = _PARAPHRASE_TEMPLATES[i % len(_PARAPHRASE_TEMPLATES)]
            text = template.format(
                criterion_name=criterion.name,
                description=description,
                competency_description=competency_description,
            )
            tag = f"synthetic_{competency_code}_{criterion.id[:8]}_{i}"
            fragments.append(
                SyntheticFragment(
                    criterion_id=criterion.id,
                    competency_code=competency_code,
                    criterion_name=criterion.name,
                    text=text,
                    tag=tag,
                )
            )
    return fragments


def _generate_llm_synthetics(
    criteria: list[EvaluationCriterion],
    per_criterion: int,
) -> list[SyntheticFragment] | None:
    """Try to generate synthetic fragments via Gemini.

    Returns None if the LLM is not available, so the caller can fall back
    to local generation.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        return None

    try:
        from google import genai
    except ImportError:
        return None

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
    except Exception:
        return None

    fragments: list[SyntheticFragment] = []
    for criterion in criteria:
        competency = criterion.competency
        prompt = textwrap.dedent(f"""\
            Eres un simulador de fragmentos de tesis universitarias de ingenieria
            en computacion. Genera exactamente {per_criterion} parrafos distintos
            (cada uno de 80-150 palabras) que representen evidencia textual
            encontrada en una tesis/memoria de titulo que demuestra el
            cumplimiento del siguiente criterio academico:

            Competencia: {competency.code} - {competency.description}
            Criterio: {criterion.name} - {criterion.description}

            Cada parrafo debe:
            - Estar escrito en español academico formal.
            - Simular un fragmento real de una tesis (metodologia, resultados,
              conclusiones, etc.).
            - Contener terminologia tecnica relevante al criterio.
            - NO mencionar explicitamente "competencia", "criterio" ni
              "perfil de egreso".

            Responde SOLO con los parrafos, separados por una linea en blanco.
            No agregues numeracion, titulos ni explicaciones.
        """)

        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            text = response.text or ""
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            paragraphs = paragraphs[:per_criterion]

            for i, paragraph in enumerate(paragraphs):
                tag = f"synthetic_llm_{competency.code}_{criterion.id[:8]}_{i}"
                fragments.append(
                    SyntheticFragment(
                        criterion_id=criterion.id,
                        competency_code=competency.code,
                        criterion_name=criterion.name,
                        text=paragraph,
                        tag=tag,
                    )
                )
        except Exception as exc:
            print(f"  [!] Gemini fallo para {competency.code}/{criterion.name}: {exc}")
            # Fall back to local for this criterion
            local = _generate_local_synthetics([criterion], per_criterion)
            fragments.extend(local)

    return fragments if fragments else None


# ── Fake chunk wrappers (match what HybridEvidenceRanker expects) ─────────

@dataclass
class _FakeChunk:
    id: str
    text: str
    token_count: int
    page: int = 0
    version: Any = None


@dataclass
class _FakeEmbedding:
    vector: list[float]


# ── Core recall evaluation ────────────────────────────────────────────────

def evaluate_recall(
    db: Session,
    period_name: str,
    top_k: int = 5,
    synthetic_per_criterion: int = 3,
) -> RecallReport:
    """Run the full recall evaluation pipeline."""

    settings = get_settings()

    # 1. Resolve period
    period = db.query(AcademicPeriod).filter(AcademicPeriod.name == period_name).first()
    if not period:
        available = [p.name for p in db.query(AcademicPeriod).all()]
        raise ValueError(
            f"No existe el periodo '{period_name}'. "
            f"Periodos disponibles: {available}"
        )

    # 2. Load criteria
    criteria = (
        db.query(EvaluationCriterion)
        .all()
    )
    if not criteria:
        raise ValueError("No hay criterios de evaluacion cargados.")

    print(f"\n{'='*60}")
    print(f"  KPI: Recall de Detección de Evidencia")
    print(f"{'='*60}")
    print(f"  Periodo: {period_name}")
    print(f"  Criterios: {len(criteria)}")
    print(f"  Top-K: {top_k}")
    print(f"  Sintéticos por criterio: {synthetic_per_criterion}")

    # 3. Generate synthetic fragments
    print(f"\n  Generando fragmentos sintéticos...")
    generation_method = "local-paraphrase"
    synthetics = None
    try:
        synthetics = _generate_llm_synthetics(criteria, synthetic_per_criterion)
    except Exception as exc:
        print(f"  [!] LLM generation failed globally: {exc}")
    if synthetics:
        generation_method = "gemini-llm"
        print(f"  [OK] {len(synthetics)} fragmentos generados con Gemini")
    else:
        synthetics = _generate_local_synthetics(criteria, synthetic_per_criterion)
        print(f"  [OK] {len(synthetics)} fragmentos generados localmente (fallback)")

    # 4. Load real chunks from the period
    from app.db.models import Document, DocumentVersion

    version_ids = [
        v.id
        for v in (
            db.query(DocumentVersion)
            .join(Document)
            .filter(
                Document.period_id == period.id,
                Document.status != "deleted",
            )
            .all()
        )
    ]

    embedding_service = EmbeddingService()
    real_chunks: list[tuple[object, object]] = []
    if version_ids:
        real_chunks = (
            db.query(DocumentChunk, ChunkEmbedding)
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .filter(
                DocumentChunk.version_id.in_(version_ids),
                ChunkEmbedding.model == embedding_service.model_name,
                ChunkEmbedding.dimensions == embedding_service.dimensions,
            )
            .all()
        )

    print(f"  Chunks reales cargados: {len(real_chunks)}")

    # 5. Embed synthetic fragments and build mixed pool
    print(f"  Generando embeddings de fragmentos sintéticos...")
    synthetic_chunk_map: dict[str, SyntheticFragment] = {}
    synthetic_tuples: list[tuple[object, object]] = []
    for fragment in synthetics:
        fake_chunk = _FakeChunk(
            id=fragment.tag,
            text=fragment.text,
            token_count=len(fragment.text.split()),
        )
        fake_embedding = _FakeEmbedding(
            vector=embedding_service.embed(fragment.text),
        )
        synthetic_chunk_map[fragment.tag] = fragment
        synthetic_tuples.append((fake_chunk, fake_embedding))

    mixed_pool = list(real_chunks) + synthetic_tuples
    print(f"  Pool total (real + sintético): {len(mixed_pool)} chunks")

    # 6. Run retrieval for each criterion and measure recall
    ranker = HybridEvidenceRanker(embedding_service)
    criteria_results: list[CriterionRecallResult] = []

    print(f"\n  Evaluando recall por criterio...")
    print(f"  {'-'*56}")

    for criterion in criteria:
        # Build query text the same way analysis.py does
        query_text = "\n".join([
            criterion.name,
            criterion.description,
            criterion.competency.description,
        ])
        query_vector = embedding_service.embed(query_text)

        # Rank the mixed pool
        ranked = ranker.rank(query_text, query_vector, mixed_pool)[:top_k]

        # Check which synthetic fragments were recovered
        injected_for_criterion = [
            f for f in synthetics if f.criterion_id == criterion.id
        ]
        injected_tags = {f.tag for f in injected_for_criterion}

        recovered_tags: set[str] = set()
        recovered_ranks: list[int] = []
        for rank_pos, ranked_chunk in enumerate(ranked, start=1):
            chunk_id = getattr(ranked_chunk.chunk, "id", None)
            if chunk_id in injected_tags:
                recovered_tags.add(chunk_id)
                recovered_ranks.append(rank_pos)

        injected_count = len(injected_for_criterion)
        recovered_count = len(recovered_tags)
        recall = recovered_count / injected_count if injected_count > 0 else 0.0

        result = CriterionRecallResult(
            criterion_id=criterion.id,
            competency_code=criterion.competency.code,
            criterion_name=criterion.name,
            injected=injected_count,
            recovered=recovered_count,
            recall=recall,
            recovered_ranks=recovered_ranks,
        )
        criteria_results.append(result)

        status_icon = "[OK]" if recall >= 0.8 else ("[!!]" if recall >= 0.5 else "[XX]")
        print(
            f"  {status_icon} {criterion.competency.code:6s} | "
            f"Recall: {recall:.2f} ({recovered_count}/{injected_count}) | "
            f"{criterion.name[:45]}"
        )

    # 7. Aggregate global recall
    total_injected = sum(r.injected for r in criteria_results)
    total_recovered = sum(r.recovered for r in criteria_results)
    global_recall = total_recovered / total_injected if total_injected > 0 else 0.0

    baseline = 0.60
    target = 0.80
    if global_recall >= target:
        status = "CUMPLE OBJETIVO"
    elif global_recall >= baseline:
        status = "SOBRE LINEA BASE"
    else:
        status = "BAJO LINEA BASE"

    print(f"  {'-'*56}")
    print(f"\n  RECALL GLOBAL: {global_recall:.4f}")
    print(f"  Recuperados: {total_recovered}/{total_injected}")
    print(f"  Línea base: {baseline} | Objetivo: >= {target}")
    print(f"  Estado: {status}")
    print(f"  Método de generación: {generation_method}")
    print(f"{'='*60}\n")

    report = RecallReport(
        period_name=period_name,
        top_k=top_k,
        synthetic_per_criterion=synthetic_per_criterion,
        total_criteria=len(criteria),
        total_real_chunks=len(real_chunks),
        total_injected=total_injected,
        total_recovered=total_recovered,
        global_recall=global_recall,
        baseline=baseline,
        target=target,
        status=status,
        criteria_results=criteria_results,
        generated_at=datetime.utcnow().isoformat(),
        generation_method=generation_method,
    )
    return report


def save_report(report: RecallReport, output_path: Path) -> None:
    """Persist the recall report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(report)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Reporte guardado en: {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="KPI: Recall de detección de evidencia (Synthetic Evidence Injection)",
    )
    parser.add_argument(
        "--period",
        required=True,
        help="Nombre del período académico a evaluar (ej: '2025-1').",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Cantidad de resultados top-K para verificar (default: 5).",
    )
    parser.add_argument(
        "--synthetic-per-criterion",
        type=int,
        default=3,
        help="Fragmentos sintéticos a inyectar por criterio (default: 3).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Ruta para guardar el reporte JSON (default: data/recall_kpi_report.json).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = evaluate_recall(
            db,
            period_name=args.period,
            top_k=args.top_k,
            synthetic_per_criterion=args.synthetic_per_criterion,
        )
        output_path = Path(args.output) if args.output else (BACKEND_DIR / "data" / "recall_kpi_report.json")
        save_report(report, output_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
