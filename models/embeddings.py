"""Embedding model — turns text into vectors for semantic memory."""
from __future__ import annotations


class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed. Record the model name on each MemoryItem so
        consolidation can re-embed everything if you swap models later."""
        raise NotImplementedError("Wire an embedding model; see ARCHITECTURE.md (Stores)")
