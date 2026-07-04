"""Cross-encoder reranker — reorders fused candidates by true relevance."""
from __future__ import annotations

from memory.schema import RetrievalCandidate


class Reranker:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def rerank(self, query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        """Score each candidate against the query with a cross-encoder and
        return them reordered. MUST degrade gracefully: if the model is
        unavailable, return candidates unchanged rather than raising — the
        pipeline is built to run without a reranker.
        """
        raise NotImplementedError("Wire a cross-encoder; see ARCHITECTURE.md (Read path)")
