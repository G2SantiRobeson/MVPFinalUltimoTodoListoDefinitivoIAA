from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

from app.services.embeddings import EmbeddingService


TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")

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
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens = TOKEN_RE.findall(normalized)
    return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]


def expand_tokens(tokens: list[str]) -> list[str]:
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
            weight = 0.5
        elif len(token) >= 9:
            weight = 1.35
        elif len(token) >= 6:
            weight = 1.15
        else:
            weight = 1.0
        weights[token] = max(weights.get(token, 0.0), weight)
    return weights


def lexical_overlap(query_tokens: list[str], chunk_tokens: list[str]) -> tuple[float, list[str]]:
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
    return min(1.0, coverage * 0.85 + jaccard * 0.15), matched[:12]


def phrase_overlap(query_tokens: list[str], chunk_tokens: list[str]) -> float:
    if len(query_tokens) < 2 or len(chunk_tokens) < 2:
        return 0.0

    chunk_bigrams = set(zip(chunk_tokens, chunk_tokens[1:], strict=False))
    query_bigrams = set(zip(query_tokens, query_tokens[1:], strict=False))
    if not query_bigrams:
        return 0.0
    return len(query_bigrams.intersection(chunk_bigrams)) / len(query_bigrams)


def section_signal(chunk_tokens: list[str]) -> float:
    if not chunk_tokens:
        return 0.0
    matches = len(set(chunk_tokens).intersection(ACADEMIC_SECTION_TERMS))
    return min(1.0, matches / 3)


class HybridEvidenceRanker:
    """Ranks candidate chunks with vector and lexical evidence.

    This is still lightweight, but it is much less fragile than using only the
    development embedding. It gives explicit reasons for every evidence match.
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
            hybrid = semantic * 0.42 + lexical * 0.42 + phrase * 0.10 + section * 0.06
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
