"""Semantic store — atomic 'memory items' with vector search.

Hybrid strategy: rather than hand-rolling embedding + dedup + supersede, this is
backed by Mem0 (self-hostable), which extracts durable facts from turns,
deduplicates/updates them, and serves vector search — the reconcile-on-write the
naive path skips. It degrades gracefully: if Mem0 (or its configured
LLM/embedder) is unavailable, every method becomes a safe no-op / empty result,
so the rest of the layer keeps running on the episodic keyword + recency
retrievers. Configure Mem0 via env (an API key, or a local Ollama setup) to
light this up.

Swap target: replace the Mem0 calls with a direct sqlite-vec / Chroma index if
you later want to own this layer — the method surface stays identical.
"""
from __future__ import annotations

import os

from memory.schema import MemoryItem, RetrievalCandidate, Source


class SemanticStore:
    def __init__(self, vector_dir, embedder=None, mem0_config: dict | None = None):
        self.vector_dir = str(vector_dir)
        self.embedder = embedder
        self._mem = None
        self.available = False
        self._init_mem0(mem0_config)

    def _init_mem0(self, mem0_config) -> None:
        try:
            from mem0 import Memory
        except Exception:
            return  # Mem0 not installed -> degrade to the episodic-only spine.
        try:
            cfg = mem0_config or _default_mem0_config(self.vector_dir)
            self._mem = Memory.from_config(cfg) if cfg else Memory()
            self.available = True
        except Exception:
            # Present but unconfigured (e.g. no LLM/key) — stay degraded.
            self._mem = None
            self.available = False

    # --- write --------------------------------------------------------------
    def add_turn(self, user_input: str, assistant_reply: str, scope: str | None = None) -> None:
        """Hand a completed exchange to Mem0; it extracts + dedups + updates the
        durable facts. Never crashes a turn — a failure here must not lose the
        already-appended raw episode."""
        if not self.available:
            return
        try:
            self._mem.add(
                [{"role": "user", "content": user_input or ""},
                 {"role": "assistant", "content": assistant_reply or ""}],
                user_id=scope or "default",
            )
        except Exception:
            pass

    def upsert(self, item: MemoryItem) -> None:
        if not self.available:
            return
        try:
            self._mem.add(item.content, user_id=item.scope or "default")
        except Exception:
            pass

    # --- read ---------------------------------------------------------------
    def search(self, query: str, scope: str | None = None, k: int = 20) -> list[RetrievalCandidate]:
        if not self.available:
            return []
        try:
            res = self._mem.search(query, user_id=scope or "default", limit=k)
        except Exception:
            return []
        rows = res.get("results", res) if isinstance(res, dict) else res
        out: list[RetrievalCandidate] = []
        for rank, m in enumerate(rows or []):
            content = (m.get("memory") or m.get("text") or "") if isinstance(m, dict) else str(m)
            if not content:
                continue
            score = float(m.get("score", 0.0) or 0.0) if isinstance(m, dict) else 0.0
            out.append(RetrievalCandidate(
                ref_id=str(m.get("id", f"mem-{rank}")) if isinstance(m, dict) else f"mem-{rank}",
                content=content, source=Source.VECTOR, scope=scope, rank=rank,
                raw_score=score, token_estimate=max(1, len(content) // 4),
            ))
        return out

    def find_similar(self, item: MemoryItem, threshold: float = 0.9) -> list[MemoryItem]:
        # Mem0 does its own dedup on add(); explicit similarity is optional here.
        return []

    def touch(self, item_id: str) -> None:
        return  # Mem0 manages its own access stats.

    def archive(self, item_id: str) -> None:
        if not self.available:
            return
        try:
            self._mem.delete(memory_id=item_id)
        except Exception:
            pass


def _default_mem0_config(vector_dir: str) -> dict | None:
    """A local-first Mem0 config against Ollama; None (Mem0's OpenAI defaults)
    when an OpenAI key is present. The call site wraps init in try/except, so a
    config that can't connect simply degrades."""
    if os.environ.get("OPENAI_API_KEY"):
        return None  # let Mem0 use its OpenAI defaults
    return {
        "llm": {"provider": "ollama", "config": {"model": "qwen3:14b"}},
        "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text"}},
        "vector_store": {"provider": "chroma", "config": {"path": f"{vector_dir}/mem0"}},
    }
