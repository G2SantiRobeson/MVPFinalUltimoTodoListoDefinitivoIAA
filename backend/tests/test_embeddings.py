import sys
import types

from app.services.embeddings import EmbeddingService


def test_local_embedding_is_deterministic_and_normalized():
    service = EmbeddingService(dimensions=16)

    first = service.embed("diseno de software y trazabilidad academica")
    second = service.embed("diseno de software y trazabilidad academica")

    assert first == second
    assert len(first) == 16
    assert abs(service.cosine(first, first) - 1.0) < 0.000001


def test_requested_cuda_falls_back_to_cpu_when_cuda_is_unavailable(monkeypatch):
    torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)

    device, warning = EmbeddingService._resolve_device("cuda")

    assert device == "cpu"
    assert "CUDA no esta disponible" in warning


def test_requested_cuda_uses_cuda_when_available(monkeypatch):
    torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: True),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)

    device, warning = EmbeddingService._resolve_device("cuda")

    assert device == "cuda"
    assert warning is None
