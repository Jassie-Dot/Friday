from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from collections import Counter

from app.core.config import Settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        counts: Counter[int] = Counter()
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            counts[index] += 1

        vector = [0.0] * self.dimensions
        if not counts:
            return vector

        norm = math.sqrt(sum(value * value for value in counts.values()))
        for index, value in counts.items():
            vector[index] = value / norm
        return vector


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_path: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install the embeddings extra to use this backend."
            ) from exc

        model_name = model_path or "all-MiniLM-L6-v2"
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbeddingProvider(settings.embedding_model_path)
    return HashEmbeddingProvider()
