"""Cross-encoder reranker — reorders fused candidates by true relevance.

Loads a local cross-encoder via sentence-transformers on first use and sets
cand.rerank_score so the signal survives retrieval's final re-sort. Degrades
gracefully: if sentence-transformers or the model isn't available it returns
candidates unchanged (identity passthrough) — the pipeline runs with or without
a reranker.

Default is a small, fast MiniLM cross-encoder. For best quality while staying
local-first, upgrade `model_name` to a Qwen3-Reranker checkpoint.
"""
from __future__ import annotations

import math

from memory.schema import RetrievalCandidate


def _sigmoid(x: float) -> float:
    # Squash raw cross-encoder logits (~±11) into [0,1] so rerank_score is
    # comparable with the other normalised signals in score_final.
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", **opts):
        self.model_name = model_name
        self.opts = opts
        self._model = None
        self._tried = False

    def _load(self):
        if self._tried:
            return self._model
        self._tried = True
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        except Exception:
            self._model = None  # dep/model absent -> identity passthrough
        return self._model

    def rerank(self, query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        if not candidates:
            return candidates
        model = self._load()
        if model is None:
            return candidates  # graceful identity passthrough
        try:
            scores = model.predict([(query, c.content) for c in candidates])
            for c, s in zip(candidates, scores):
                c.rerank_score = _sigmoid(float(s))
            candidates.sort(key=lambda c: c.rerank_score, reverse=True)
        except Exception:
            pass
        return candidates
