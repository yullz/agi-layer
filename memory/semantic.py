"""Semantic store — vector index of atomic memory items.

Backed by sqlite-vec / Chroma / LanceDB. Holds distilled facts and summaries
with their embeddings, importance, and access stats.
"""
from __future__ import annotations

from memory.schema import MemoryItem, RetrievalCandidate


class SemanticStore:
    def __init__(self, vector_dir, embedder):
        self.vector_dir = vector_dir
        self.embedder = embedder
        raise NotImplementedError("Init the vector store; see ARCHITECTURE.md (Stores)")

    def upsert(self, item: MemoryItem) -> None:
        raise NotImplementedError

    def search(self, query: str, scope: str | None = None, k: int = 20) -> list[RetrievalCandidate]:
        """Embed the query and return top-k by cosine similarity, filtered by
        scope. Return RetrievalCandidate objects (source=VECTOR)."""
        raise NotImplementedError

    def find_similar(self, item: MemoryItem, threshold: float = 0.9) -> list[MemoryItem]:
        """Used by the write path to detect duplicates/conflicts before insert."""
        raise NotImplementedError

    def touch(self, item_id: str) -> None:
        """Bump last_accessed / access_count when an item is retrieved.
        This is the reinforcement half of the forgetting curve."""
        raise NotImplementedError

    def archive(self, item_id: str) -> None:
        """Evict a cold item from the hot index (it stays in episodic)."""
        raise NotImplementedError
