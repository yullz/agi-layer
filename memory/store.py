"""MemoryStore — the single boundary the core depends on.

The core calls exactly three methods: retrieve, write, consolidate. Every
storage decision (which DB, which vector index, how extraction works) lives
behind this facade, so you can rebuild anything underneath without touching the
core. Keep this interface small and stable — it is the most important line in
the whole system.
"""
from __future__ import annotations

import time

from memory import retrieval
from memory.schema import ContextBundle, MemoryItem, Source, Turn
from memory.scope import is_sensitive_scope


class MemoryStore:
    def __init__(
        self,
        *,
        episodic,
        semantic,
        graph,
        procedural,
        embedder,
        write_pipeline,
        consolidator,
        reranker=None,
        half_life_days: float = 30.0,
        budget_tokens: int = 6000,
        write_async: bool = True,
    ):
        self.episodic = episodic
        self.semantic = semantic
        self.graph = graph
        self.procedural = procedural
        self.embedder = embedder
        self.write_pipeline = write_pipeline
        self.consolidator = consolidator
        self.reranker = reranker
        self.half_life_days = half_life_days
        self.budget_tokens = budget_tokens
        self.write_async = write_async

    # --- READ ---------------------------------------------------------------
    def retrieve(self, query: str, scope: str | None, budget_tokens: int | None = None,
                 for_external: bool = False) -> ContextBundle:
        """Assemble the retrievers and run the pipeline. The retrievers are
        thin adapters over the stores, so retrieval.py stays storage-agnostic.

        `for_external=True` (the answer is going to a non-local model) drops any
        candidate from a sensitive scope before it can leave the machine."""
        retrievers = [
            _VectorRetriever(self.semantic),
            _KeywordRetriever(self.episodic),
            _GraphRetriever(self.graph),
            _RecencyRetriever(self.episodic),
        ]
        bundle = retrieval.retrieve(
            query,
            scope=scope,
            budget_tokens=budget_tokens or self.budget_tokens,
            retrievers=retrievers,
            reranker=self.reranker,
            now=time.time(),
            half_life_days=self.half_life_days,
        )
        # Privacy: never ship sensitive-scope memory to an external model.
        if for_external:
            safe = [c for c in bundle.items if not is_sensitive_scope(c.scope)]
            if len(safe) != len(bundle.items):
                bundle.items = safe
                bundle.provenance = [c.ref_id for c in safe]
                bundle.token_count = sum(c.token_estimate or max(1, len(c.content) // 4)
                                         for c in safe)
        # Reinforce what we actually used: bump importance / access stats so
        # frequently-useful memories resist decay (the other half of forgetting).
        for cand in bundle.items:
            # Only VECTOR candidates map to semantic MemoryItem ids; keyword/
            # graph/recency ref_ids are Episode ids and don't belong here.
            if cand.source != Source.VECTOR:
                continue
            try:
                self.semantic.touch(cand.ref_id)
            except Exception:
                pass
        return bundle

    # --- WRITE --------------------------------------------------------------
    def write(self, turn: Turn) -> None:
        """Persist the turn. Raw episodes are appended synchronously (cheap);
        extraction / dedup / upsert runs on the write pipeline, off the hot path
        when write_async is set."""
        self.write_pipeline.append_raw(turn)           # fast, lossless, synchronous
        if self.write_async:
            self.write_pipeline.enqueue_ingest(turn)   # background extract + upsert
        else:
            self.write_pipeline.ingest(turn)

    # --- BACKGROUND ---------------------------------------------------------
    def consolidate(self) -> None:
        """Kick the background 'sleep' pass. Called by the scheduler."""
        self.consolidator.run()

    def close(self) -> None:
        for store in (self.episodic, self.semantic, self.graph, self.procedural):
            closer = getattr(store, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass

    # --- memory control (curate what it knows) ------------------------------
    def remember(self, content: str, scope: str | None = None):
        """Store a durable fact (reconciled) and update the graph from it."""
        item_id = None
        fn = getattr(self.semantic, "remember", None)
        try:
            if callable(fn):
                item_id = fn(content, scope)
            else:
                self.semantic.upsert(MemoryItem(content=content, scope=scope))
        except Exception:
            pass
        try:
            self.write_pipeline._update_graph(
                Turn(user_input=content, assistant_reply="", scope=scope))
        except Exception:
            pass
        return item_id

    def forget(self, query: str, scope: str | None = None) -> int:
        fn = getattr(self.semantic, "forget", None)
        try:
            return fn(query, scope) if callable(fn) else 0
        except Exception:
            return 0

    def correct(self, old_query: str, new_content: str, scope: str | None = None) -> bool:
        fn = getattr(self.semantic, "correct", None)
        try:
            return fn(old_query, new_content, scope) if callable(fn) else False
        except Exception:
            return False

    def provenance(self, query: str, scope: str | None = None) -> list:
        fn = getattr(self.semantic, "provenance", None)
        try:
            return fn(query, scope) if callable(fn) else []
        except Exception:
            return []


# --- retriever adapters (store -> retrieval.Retriever) ----------------------
# These translate each store's native call into the uniform Retriever shape the
# pipeline expects. Their `search` must return RetrievalCandidate objects.

class _VectorRetriever:
    def __init__(self, semantic):
        self.semantic = semantic

    def search(self, query, scope, k):
        return self.semantic.search(query, scope=scope, k=k)


class _KeywordRetriever:
    def __init__(self, episodic):
        self.episodic = episodic

    def search(self, query, scope, k):
        # EpisodicStore.search should return RetrievalCandidate(source=KEYWORD).
        return self.episodic.search(query, scope=scope, limit=k)


class _GraphRetriever:
    def __init__(self, graph):
        self.graph = graph

    def search(self, query, scope, k):
        # Prefer matching the query against KNOWN entity names (case-insensitive,
        # multi-word) so read/write entity detection agree; fall back to the
        # capitalised-token heuristic only if the store can't do it.
        finder = getattr(self.graph, "entities_in_text", None)
        entities = finder(query, scope) if callable(finder) else _entity_mentions(query)
        if not entities:
            return []
        return self.graph.neighbors(entities, scope=scope, hops=2)[:k]


class _RecencyRetriever:
    def __init__(self, episodic):
        self.episodic = episodic

    def search(self, query, scope, k):
        # Empty terms => most-recent-first (source=RECENCY). This is the
        # "what were we just doing" signal.
        return self.episodic.search("", scope=scope, limit=k)


def _entity_mentions(query: str) -> list[str]:
    """Placeholder entity extraction. Replace with an NER pass or a match
    against the graph's known entity names for real multi-hop retrieval."""
    return [tok.strip(".,:;!?") for tok in query.split() if tok[:1].isupper()]
