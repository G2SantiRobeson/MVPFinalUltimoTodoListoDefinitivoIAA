from app.services.embeddings import EmbeddingService


def test_local_embedding_is_deterministic_and_normalized():
    service = EmbeddingService(dimensions=16)

    first = service.embed("diseno de software y trazabilidad academica")
    second = service.embed("diseno de software y trazabilidad academica")

    assert first == second
    assert len(first) == 16
    assert abs(service.cosine(first, first) - 1.0) < 0.000001
