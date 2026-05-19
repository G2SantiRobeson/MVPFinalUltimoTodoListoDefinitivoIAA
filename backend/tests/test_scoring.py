from dataclasses import dataclass

from app.services.embeddings import EmbeddingService
from app.services.scoring import HybridEvidenceRanker, tokenize


@dataclass
class FakeChunk:
    text: str
    token_count: int


@dataclass
class FakeEmbedding:
    vector: list[float]


def test_tokenize_normalizes_accents_and_stopwords():
    assert "diseno" in tokenize("Diseño de software para la solución")
    assert "software" in tokenize("Diseño de software para la solución")
    assert "para" not in tokenize("Diseño de software para la solución")


def test_hybrid_ranker_prefers_traceable_academic_evidence():
    service = EmbeddingService(dimensions=32)
    query = "Diseña software, incluyendo arquitectura, diseño detallado y buenas prácticas"
    relevant = FakeChunk(
        text=(
            "La metodologia describe la arquitectura del software, sus componentes, "
            "el diseno detallado y las buenas practicas aplicadas en la implementacion."
        ),
        token_count=20,
    )
    irrelevant = FakeChunk(
        text="El documento agradece el apoyo familiar y presenta antecedentes administrativos.",
        token_count=10,
    )

    chunks = [
        (irrelevant, FakeEmbedding(service.embed(irrelevant.text))),
        (relevant, FakeEmbedding(service.embed(relevant.text))),
    ]

    ranked = HybridEvidenceRanker(service).rank(query, service.embed(query), chunks)

    assert ranked[0].chunk is relevant
    assert ranked[0].hybrid_score > ranked[1].hybrid_score
    assert {"software", "arquitectura", "diseno"}.intersection(ranked[0].matched_terms)
