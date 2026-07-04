"""Retrieval pipeline — the highest-leverage code in the system.

Whether the layer feels smart is decided here. The job: given a query and the
active scope, gather candidates from several heterogeneous retrievers, fuse
their rankings, rerank for true relevance, then pack the best of them into a
fixed token budget.

Design notes:
  * We fuse with Reciprocal Rank Fusion (RRF), NOT by comparing raw scores.
    A cosine similarity, a BM25 score, and a graph-distance score are not on
    the same scale — RRF only uses *rank*, so it combines them cleanly.
  * Final ordering multiplies relevance by importance and a recency decay, so
    an old-but-central fact can still beat a fresh-but-trivial one, and vice
    versa. The weights are the main tuning knobs.
  * Budget packing is greedy by final score. Whatever doesn't fit is compressed
    into a one-line note so the model knows it existed.
  * Every stage degrades gracefully: no reranker -> skip rerank; a retriever
    that errors -> drop its list, keep the rest. Retrieval must never crash a
    turn.

This module operates purely on the abstractions in schema.py plus a Retriever
protocol, so it has no dependency on any concrete store. That is deliberate —
it is the one piece worth getting exactly right, and it should be testable in
isolation.
"""
from __future__ import annotations

import math
from typing import Callable, Protocol

from memory.schema import ContextBundle, RetrievalCandidate


class Retriever(Protocol):
    """Anything that can return a ranked list of candidates for a query."""
    def search(self, query: str, scope: str | None, k: int) -> list[RetrievalCandidate]:
        ...


def reciprocal_rank_fusion(
    lists: list[list[RetrievalCandidate]],
    k: int = 60,
) -> list[RetrievalCandidate]:
    """Combine several ranked lists into one.

    RRF score for an item = sum, over the lists it appears in, of
    1 / (k + rank), where rank is 0-based within that list. k dampens the pull
    of top ranks so no single retriever dominates. Deduplicates by ref_id,
    accumulating the contribution when the same item shows up in several lists
    (which is exactly the signal we want — agreement across retrievers).
    """
    fused: dict[str, RetrievalCandidate] = {}
    for ranked in lists:
        for rank, cand in enumerate(ranked):
            contribution = 1.0 / (k + rank)
            existing = fused.get(cand.ref_id)
            if existing is None:
                cand.fused_score = contribution
                fused[cand.ref_id] = cand
            else:
                existing.fused_score += contribution
    return sorted(fused.values(), key=lambda c: c.fused_score, reverse=True)


def recency_weight(age_seconds: float, half_life_days: float = 30.0) -> float:
    """Exponential decay in [0, 1]. An item exactly one half-life old scores
    0.5; brand-new ~1.0; ancient -> 0. Keeps retrieval biased toward what's
    currently relevant without ever fully erasing old facts."""
    half_life_seconds = half_life_days * 86400.0
    if half_life_seconds <= 0:
        return 1.0
    return math.pow(0.5, max(0.0, age_seconds) / half_life_seconds)


def score_final(
    cand: RetrievalCandidate,
    now: float,
    half_life_days: float,
    w_relevance: float = 1.0,
    w_importance: float = 0.6,
    w_recency: float = 0.4,
    w_rerank: float = 1.0,
) -> float:
    """Blend relevance (fusion), rerank signal, importance, and recency into one
    comparable score used for budget packing. When retrieval feels off, this is
    the first place to tune.

    A reranker persists its judgement by setting cand.rerank_score (0 when no
    reranker ran), so a reranker's reordering is no longer silently overwritten
    by this final re-sort."""
    rec = recency_weight(now - cand.created_at, half_life_days)
    return (
        w_relevance * cand.fused_score
        + w_rerank * cand.rerank_score
        + w_importance * cand.importance
        + w_recency * rec
    )


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Swap in the target model's real
    tokenizer if you need precision right at the budget boundary."""
    return max(1, len(text) // 4)


def budget_pack(
    candidates: list[RetrievalCandidate],
    budget_tokens: int,
    summarize: Callable[[list[RetrievalCandidate]], str] | None = None,
) -> ContextBundle:
    """Greedily pack the highest-scoring candidates under the token budget.

    Candidates must already be sorted by final_score (desc). Whatever spills
    over is optionally compressed by `summarize(overflow) -> str` into a single
    line so the model stays aware of it; without a summarizer it is noted by
    count only. Good packing beats a bigger model — don't skip the overflow
    note, a silent drop is how the layer 'forgets' mid-conversation.
    """
    picked: list[RetrievalCandidate] = []
    overflow: list[RetrievalCandidate] = []
    used = 0

    for cand in candidates:
        cost = cand.token_estimate or _estimate_tokens(cand.content)
        if used + cost <= budget_tokens:
            picked.append(cand)
            used += cost
        else:
            overflow.append(cand)

    if overflow and summarize is not None:
        dropped = summarize(overflow)
    elif overflow:
        dropped = f"[{len(overflow)} more relevant memories omitted for space]"
    else:
        dropped = ""

    return ContextBundle(
        items=picked,
        token_count=used,
        summary_of_dropped=dropped,
        provenance=[c.ref_id for c in picked],
    )


def retrieve(
    query: str,
    *,
    scope: str | None,
    budget_tokens: int,
    retrievers: list[Retriever],
    now: float,
    reranker=None,
    summarize: Callable[[list[RetrievalCandidate]], str] | None = None,
    half_life_days: float = 30.0,
    per_retriever_k: int = 20,
    rrf_k: int = 60,
) -> ContextBundle:
    """Run the full pipeline: gather -> fuse -> rerank -> score -> pack.

    `retrievers` is the set of strategies to run (vector, keyword, graph,
    recency), injected by MemoryStore. Each is called independently and its
    failure is isolated. Returns a ready-to-inject ContextBundle.
    """
    # 1. Gather from every retriever, isolating failures so one dead index
    #    (or an unreachable embedding service) can't kill the turn.
    lists: list[list[RetrievalCandidate]] = []
    for r in retrievers:
        try:
            hits = r.search(query, scope, per_retriever_k)
        except Exception:
            continue
        if hits:
            lists.append(hits)

    if not lists:
        return ContextBundle()

    # 2. Fuse heterogeneous rankings into one list (rank-based, scale-free).
    fused = reciprocal_rank_fusion(lists, k=rrf_k)

    # 3. Rerank the fused list for true query relevance (optional, graceful).
    if reranker is not None:
        try:
            fused = reranker.rerank(query, fused)
        except Exception:
            pass  # keep the fused order rather than failing the turn

    # 4. Blend in importance + recency, then sort for packing.
    for cand in fused:
        cand.final_score = score_final(cand, now, half_life_days)
    fused.sort(key=lambda c: c.final_score, reverse=True)

    # 5. Greedily pack under the budget, compressing the tail.
    return budget_pack(fused, budget_tokens, summarize=summarize)
