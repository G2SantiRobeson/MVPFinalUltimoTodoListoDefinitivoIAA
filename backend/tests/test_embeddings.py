import sys
import types

import pytest

import app.services.embeddings as embeddings
from app.services.embeddings import EmbeddingService


def embedding_settings():
    return types.SimpleNamespace(
        embedding_provider="bge-m3",
        embedding_model_name="BAAI/bge-m3",
        embedding_dimensions=1024,
        embedding_max_sequence_length=8192,
        embedding_device="cpu",
    )


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


def test_missing_sentence_transformers_reports_install_command(monkeypatch):
    monkeypatch.setattr(embeddings, "get_settings", embedding_settings)

    def missing_package(*args, **kwargs):
        raise ModuleNotFoundError(
            "No module named 'sentence_transformers'",
            name="sentence_transformers",
        )

    monkeypatch.setattr(embeddings, "_load_sentence_transformer", missing_package)

    with pytest.raises(RuntimeError, match="Desde la carpeta backend"):
        EmbeddingService()


def test_model_load_failure_reports_actual_detail(monkeypatch):
    monkeypatch.setattr(embeddings, "get_settings", embedding_settings)

    def cuda_failure(*args, **kwargs):
        raise RuntimeError("CUDA driver no disponible")

    monkeypatch.setattr(embeddings, "_load_sentence_transformer", cuda_failure)

    with pytest.raises(RuntimeError, match="CUDA driver no disponible"):
        EmbeddingService()
