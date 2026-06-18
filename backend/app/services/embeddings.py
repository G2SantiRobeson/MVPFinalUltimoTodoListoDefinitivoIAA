from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


SENTENCE_TRANSFORMER_PROVIDERS = {
    "auto",
    "sentence-transformers",
    "sentence_transformers",
    "bge-m3",
    "bge_m3",
}


TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")


@lru_cache(maxsize=4)
def _load_sentence_transformer(
    model_name: str,
    max_sequence_length: int,
    device: str | None,
) -> Any:
    from sentence_transformers import SentenceTransformer

    kwargs = {"device": device} if device else {}
    model = SentenceTransformer(model_name, **kwargs)
    if max_sequence_length > 0:
        if hasattr(model, "max_seq_length"):
            model.max_seq_length = max_sequence_length
        tokenizer = getattr(model, "tokenizer", None)
        if tokenizer is not None and hasattr(tokenizer, "model_max_length"):
            tokenizer.model_max_length = max_sequence_length
    return model


class EmbeddingService:
    """Embedding service with a real AI provider and deterministic fallback.

    Preferred provider: BAAI/bge-m3 via Sentence-Transformers for multilingual
    semantic similarity. Fallback: local hash embedding for demos/offline runs.
    """

    def __init__(self, dimensions: int | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.provider = settings.embedding_provider.lower()
        self.model_name = "local-hash-embedding"
        self.model = None
        self.fallback_reason: str | None = None
        self.max_sequence_length = settings.embedding_max_sequence_length
        self.device, self.device_warning = self._resolve_device(device or settings.embedding_device)

        if dimensions is not None:
            self.provider = "local"
            self.dimensions = dimensions
            self.max_sequence_length = 0
            self.device = "cpu"
            self.device_warning = None
            return

        if self.provider in SENTENCE_TRANSFORMER_PROVIDERS:
            try:
                self.model = _load_sentence_transformer(
                    settings.embedding_model_name,
                    settings.embedding_max_sequence_length,
                    self.device,
                )
                self.provider = "sentence-transformers"
                self.model_name = settings.embedding_model_name
                if hasattr(self.model, "get_embedding_dimension"):
                    self.dimensions = int(self.model.get_embedding_dimension())
                else:
                    self.dimensions = int(self.model.get_sentence_embedding_dimension())
                if self.dimensions != settings.embedding_dimensions:
                    raise RuntimeError(
                        f"El modelo {self.model_name} entrega {self.dimensions} dimensiones, "
                        f"pero la configuracion espera {settings.embedding_dimensions}."
                    )
                return
            except Exception as exc:
                if self.provider in SENTENCE_TRANSFORMER_PROVIDERS - {"auto"}:
                    if isinstance(exc, ModuleNotFoundError) and exc.name == "sentence_transformers":
                        raise RuntimeError(
                            "No esta instalado Sentence-Transformers. Desde la carpeta backend, "
                            'ejecuta: python -m pip install -e ".[ai]" y reinicia la API.'
                        ) from exc

                    detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
                    raise RuntimeError(
                        f"No se pudo iniciar el modelo de embeddings "
                        f"{settings.embedding_model_name} en {self.device or 'auto'}. "
                        f"Detalle: {detail}. Si el detalle menciona CUDA, configura "
                        "EMBEDDING_DEVICE=cpu o habilita una GPU compatible; si menciona "
                        "la descarga del modelo, verifica el acceso a Hugging Face."
                    ) from exc
                self.fallback_reason = str(exc)

        self.provider = "local"
        self.dimensions = settings.embedding_dimensions
        self.device = "cpu"
        if not self.device_warning and settings.embedding_provider.lower() == "auto":
            self.device_warning = "Se uso embedding local de respaldo."

    @staticmethod
    def _resolve_device(device: str | None) -> tuple[str | None, str | None]:
        normalized = (device or "auto").strip().lower()
        if normalized in {"", "auto"}:
            try:
                import torch

                return ("cuda" if torch.cuda.is_available() else "cpu", None)
            except Exception:
                return "cpu", "No se pudo consultar PyTorch; se usara CPU."
        if normalized in {"gpu", "cuda"}:
            try:
                import torch
            except Exception:
                return "cpu", "Se solicito GPU, pero PyTorch no esta disponible; se usara CPU."
            if not torch.cuda.is_available():
                return "cpu", "Se solicito GPU, pero CUDA no esta disponible en este equipo; se usara CPU."
            return "cuda", None
        if normalized == "cpu":
            return "cpu", None
        raise ValueError("Dispositivo de embeddings invalido. Usa auto, cpu, gpu o cuda.")

    def embed(self, text: str) -> list[float]:
        if self.model is not None:
            vector = self.model.encode(text, normalize_embeddings=True)
            return [float(value) for value in vector.tolist()]
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = TOKEN_RE.findall(text.lower())
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def info(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "dimensions": self.dimensions,
            "max_sequence_length": self.max_sequence_length,
            "device": self.device or "auto",
            "device_warning": self.device_warning,
            "is_real_ai": self.provider == "sentence-transformers",
            "fallback_reason": self.fallback_reason,
        }

    @staticmethod
    def cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=False))
