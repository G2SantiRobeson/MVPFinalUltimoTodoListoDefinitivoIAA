from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from app.services.embeddings import EmbeddingService


TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")

TOKEN_MIN_LENGTH = 3

NUMERIC_TOKEN_WEIGHT = 0.5
MEDIUM_TOKEN_MIN_LENGTH = 6
MEDIUM_TOKEN_WEIGHT = 1.15
LONG_TOKEN_MIN_LENGTH = 9
LONG_TOKEN_WEIGHT = 1.35
DEFAULT_TOKEN_WEIGHT = 1.0

LEXICAL_COVERAGE_WEIGHT = 0.85
LEXICAL_JACCARD_WEIGHT = 0.15
MAX_MATCHED_TERMS = 12

SECTION_SIGNAL_NORMALIZER = 3

HYBRID_SEMANTIC_WEIGHT = 0.42
HYBRID_LEXICAL_WEIGHT = 0.42
HYBRID_PHRASE_WEIGHT = 0.10
HYBRID_SECTION_WEIGHT = 0.06

STOPWORDS = {
    "a",
    "al",
    "ante",
    "bajo",
    "con",
    "contra",
    "de",
    "del",
    "desde",
    "durante",
    "e",
    "el",
    "en",
    "entre",
    "es",
    "esta",
    "este",
    "estos",
    "la",
    "las",
    "lo",
    "los",
    "mediante",
    "o",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "sobre",
    "su",
    "sus",
    "un",
    "una",
    "unas",
    "unos",
    "y",
}

ACADEMIC_SECTION_TERMS = {
    "analisis",
    "arquitectura",
    "conclusion",
    "conclusiones",
    "diseno",
    "evaluacion",
    "implementacion",
    "metodologia",
    "resultados",
    "validacion",
}

DOMAIN_EXPANSIONS = {
    "software": {"sistema", "aplicacion", "plataforma", "programa"},
    "diseno": {"arquitectura", "modelo", "componente", "modulo"},
    "arquitectura": {"diseno", "componentes", "modulos", "capas"},
    "proyecto": {"planificacion", "gestion", "requisitos", "entrega"},
    "gestion": {"planificacion", "seguimiento", "calidad", "proyecto"},
    "datos": {"base", "database", "almacenamiento", "informacion"},
    "usuario": {"usuarios", "interesados", "stakeholders", "necesidades"},
    "etica": {"responsabilidad", "impacto", "profesional", "social"},
    "equipo": {"colaboracion", "liderazgo", "trabajo"},
    "problema": {"solucion", "requerimientos", "restricciones"},
}


@dataclass(frozen=True)
class RankedChunk:
    chunk: object
    embedding: object
    hybrid_score: float
    semantic_score: float
    lexical_score: float
    phrase_score: float
    section_score: float
    matched_terms: list[str]


def normalize_text(text: str) -> str:
    """Normaliza texto eliminando tildes y convirtiendo a minúsculas."""

    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Tokeniza y filtra palabras vacías de un texto.

    Args:
        text: Texto a tokenizar.

    Returns:
        Lista de tokens relevantes (longitud > 2, sin stopwords).
    """
    normalized = normalize_text(text)
    tokens = TOKEN_RE.findall(normalized)
    return [token for token in tokens if len(token) >= TOKEN_MIN_LENGTH and token not in STOPWORDS]


def expand_tokens(tokens: list[str]) -> list[str]:
    """Expande tokens con sinónimos de dominio académico.

    Agrega términos relacionados (ej: "software" → "sistema", "aplicación").

    Args:
        tokens: Lista base de tokens.

    Returns:
        Lista expandida sin duplicados.
    """
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token not in seen:
            expanded.append(token)
            seen.add(token)
        for related in DOMAIN_EXPANSIONS.get(token, set()):
            if related not in seen:
                expanded.append(related)
                seen.add(related)
    return expanded


def _token_weights(tokens: list[str]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for token in tokens:
        if token.isdigit():
            weight = NUMERIC_TOKEN_WEIGHT
        elif len(token) >= LONG_TOKEN_MIN_LENGTH:
            weight = LONG_TOKEN_WEIGHT
        elif len(token) >= MEDIUM_TOKEN_MIN_LENGTH:
            weight = MEDIUM_TOKEN_WEIGHT
        else:
            weight = DEFAULT_TOKEN_WEIGHT
        weights[token] = max(weights.get(token, 0.0), weight)
    return weights


def lexical_overlap(query_tokens: list[str], chunk_tokens: list[str]) -> tuple[float, list[str]]:
    """Calcula la superposición léxica ponderada entre consulta y fragmento.

    Combina cobertura ponderada y similitud Jaccard.

    Args:
        query_tokens: Tokens de la consulta (criterio de evaluación).
        chunk_tokens: Tokens del fragmento de documento.

    Returns:
        Tupla (puntaje de superposición, términos coincidentes).
    """
    if not query_tokens or not chunk_tokens:
        return 0.0, []

    query_weights = _token_weights(query_tokens)
    chunk_set = set(chunk_tokens)
    matched = sorted(token for token in query_weights if token in chunk_set)
    matched_weight = sum(query_weights[token] for token in matched)
    total_weight = sum(query_weights.values()) or 1.0
    coverage = matched_weight / total_weight

    jaccard = len(set(query_tokens).intersection(chunk_set)) / max(
        len(set(query_tokens).union(chunk_set)),
        1,
    )
    score = coverage * LEXICAL_COVERAGE_WEIGHT + jaccard * LEXICAL_JACCARD_WEIGHT
    return min(1.0, score), matched[:MAX_MATCHED_TERMS]


def phrase_overlap(query_tokens: list[str], chunk_tokens: list[str]) -> float:
    """Calcula la superposición de bigramas entre consulta y fragmento.

    Detecta coincidencias de frases cortas (pares de palabras consecutivas).

    Args:
        query_tokens: Tokens de la consulta.
        chunk_tokens: Tokens del fragmento.

    Returns:
        Proporción de bigramas de la consulta presentes en el fragmento.
    """
    if len(query_tokens) < 2 or len(chunk_tokens) < 2:
        return 0.0

    chunk_bigrams = set(zip(chunk_tokens, chunk_tokens[1:], strict=False))
    query_bigrams = set(zip(query_tokens, query_tokens[1:], strict=False))
    if not query_bigrams:
        return 0.0
    return len(query_bigrams.intersection(chunk_bigrams)) / len(query_bigrams)


def section_signal(chunk_tokens: list[str]) -> float:
    """Detecta si el fragmento pertenece a una sección académica relevante.

    Busca términos como "análisis", "resultados", "conclusión".

    Args:
        chunk_tokens: Tokens del fragmento.

    Returns:
        Puntaje de señal de sección (0-1).
    """
    if not chunk_tokens:
        return 0.0
    matches = len(set(chunk_tokens).intersection(ACADEMIC_SECTION_TERMS))
    return min(1.0, matches / SECTION_SIGNAL_NORMALIZER)


class HybridEvidenceRanker:
    """Ranking híbrido de fragmentos candidatos usando evidencia vectorial y léxica.

    Combina cuatro señales (semántica, léxica, frases, secciones académicas)
    para producir un score compuesto y términos coincidentes trazables.
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    def rank(
        self,
        query_text: str,
        query_vector: list[float],
        chunks: list[tuple[object, object]],
    ) -> list[RankedChunk]:
        query_tokens = expand_tokens(tokenize(query_text))
        ranked: list[RankedChunk] = []

        for chunk, embedding in chunks:
            chunk_tokens = tokenize(chunk.text)
            semantic = max(0.0, self.embedding_service.cosine(query_vector, embedding.vector))
            lexical, matched_terms = lexical_overlap(query_tokens, chunk_tokens)
            phrase = phrase_overlap(query_tokens, chunk_tokens)
            section = section_signal(chunk_tokens)

            # Semantic signal helps recall; lexical/phrase evidence prevents vague matches.
            hybrid = (
                semantic * HYBRID_SEMANTIC_WEIGHT
                + lexical * HYBRID_LEXICAL_WEIGHT
                + phrase * HYBRID_PHRASE_WEIGHT
                + section * HYBRID_SECTION_WEIGHT
            )
            hybrid = max(0.0, min(1.0, hybrid))
            ranked.append(
                RankedChunk(
                    chunk=chunk,
                    embedding=embedding,
                    hybrid_score=hybrid,
                    semantic_score=semantic,
                    lexical_score=lexical,
                    phrase_score=phrase,
                    section_score=section,
                    matched_terms=matched_terms,
                )
            )

        ranked.sort(
            key=lambda item: (
                item.hybrid_score,
                item.lexical_score,
                item.semantic_score,
                math.log1p(getattr(item.chunk, "token_count", 0)),
            ),
            reverse=True,
        )
        return ranked
