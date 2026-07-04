"""Cross-encoder reranker — reorders fused candidates by true relevance."""
from __future__ import annotations

from memory.schema import RetrievalCandidate


class Reranker:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def rerank(self, query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        """Score each candidate against the query with a cross-encoder, set
        cand.rerank_score (higher = more relevant) so the signal survives the
        final re-sort, and return them reordered.

        Phase 1: identity passthrough (no cross-encoder wired yet). Returning
        candidates unchanged honours the graceful-degradation contract — the
        pipeline runs with or without a real reranker.
        """
        return candidates
