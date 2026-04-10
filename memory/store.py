from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from core.config import Settings
from core.models import MemoryHit
from memory.embeddings import EmbeddingProvider


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            normalized[key] = value
        else:
            normalized[key] = json.dumps(value, default=str)
    return normalized


class ChromaEmbeddingAdapter(EmbeddingFunction[Documents]):
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def __call__(self, input: Documents) -> Embeddings:
        return self.provider.embed(list(input))


class MemoryStore:
    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        self._client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            embedding_function=ChromaEmbeddingAdapter(embedding_provider),
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, document: str, metadata: dict[str, Any] | None = None, memory_id: str | None = None) -> str:
        item_id = memory_id or str(uuid4())
        self._collection.add(
            documents=[document],
            metadatas=[_normalize_metadata(metadata or {})],
            ids=[item_id],
        )
        return item_id

    def query(self, text: str, limit: int = 5, where: dict[str, Any] | None = None) -> list[MemoryHit]:
        result = self._collection.query(query_texts=[text], n_results=limit, where=where)
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[MemoryHit] = []
        for index, item_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 0.0
            hits.append(
                MemoryHit(
                    id=item_id,
                    document=docs[index],
                    metadata=metas[index] or {},
                    score=max(0.0, 1.0 - distance),
                )
            )
        return hits

    def recent(self, limit: int = 20) -> list[MemoryHit]:
        result = self._collection.get(limit=limit, include=["documents", "metadatas"])
        hits: list[MemoryHit] = []
        for item_id, document, metadata in zip(
            result.get("ids", []),
            result.get("documents", []),
            result.get("metadatas", []),
            strict=False,
        ):
            hits.append(MemoryHit(id=item_id, document=document, metadata=metadata or {}, score=1.0))
        return hits
