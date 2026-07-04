"""Native semantic store — a vector index we fully own (SQLite).

The hybrid Mem0 path is great for speed, but owning this layer unlocks the memory
*intelligence* that makes the layer feel smart:
  - reconcile-on-write: dedup near-duplicates (reinforce, don't pile up) and
    supersede contradictions (temporal, never overwrite);
  - a real forgetting curve: importance x recency x frequency, with cold items
    archived out of the hot set (never deleted);
  - working vector retrieval so the read pipeline fires on all cylinders.

Retrieval is exact cosine over the (small, local) current item set. Embeddings
come from the injected Embedder when available; otherwise a deterministic,
dependency-free hashing embedding keeps everything working offline. Swap in real
embeddings for quality — the mechanics are identical.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time

from memory.extract import extract_facts
from memory.retrieval import recency_weight
from memory.schema import ItemKind, MemoryItem, RetrievalCandidate, Source

_DIM = 256
_DUP_THRESHOLD = 0.95   # >= this cosine => treat as the same item (dedup)
_SIM_LOW = 0.5          # in [_SIM_LOW, _DUP_THRESHOLD) => ask the LLM to judge


class NativeSemanticStore:
    available = True  # native store is always usable (hashing fallback offline)

    def __init__(self, vector_dir, embedder=None, extractor=None, dim: int = _DIM):
        os.makedirs(str(vector_dir), exist_ok=True)
        self.db_path = os.path.join(str(vector_dir), "semantic.db")
        self.embedder = embedder
        self.extractor = extractor
        # Cache whether the LLM extractor is usable (a probe can be a network
        # ping); re-check by rebuilding the store if the model comes online.
        self._use_llm = bool(extractor and getattr(extractor, "available", lambda: False)())
        self.dim = dim
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, content TEXT, kind TEXT, scope TEXT,
                    importance REAL, created_at REAL, last_accessed REAL,
                    access_count INTEGER, valid_from REAL, superseded_by TEXT,
                    archived INTEGER DEFAULT 0, embedding TEXT )""")
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_items_scope ON items(scope)")
            self._db.commit()

    # --- embedding ----------------------------------------------------------
    def _embed(self, text: str) -> list[float]:
        if self.embedder is not None:
            try:
                return _normalize([float(x) for x in self.embedder.embed([text])[0]])
            except Exception:
                pass
        return _hash_embed(text, self.dim)

    # --- write --------------------------------------------------------------
    def add_turn(self, user_input: str, assistant_reply: str, scope=None) -> None:
        """Extract candidate facts and reconcile each: dedup a near-duplicate
        (reinforce), supersede a contradiction (when an LLM extractor is wired),
        otherwise insert. Falls back to heuristic extraction offline."""
        facts = None
        if self._use_llm:
            try:
                facts = self.extractor.extract(user_input, assistant_reply)
            except Exception:
                facts = None
        for fact in (facts or extract_facts(user_input)):
            self._reconcile(fact, scope)

    def _reconcile(self, content: str, scope) -> None:
        emb = self._embed(content)
        best, best_sim = self._nearest(emb, scope)
        if best is not None and best_sim >= _DUP_THRESHOLD:
            self.touch(best["id"])           # near-identical -> reinforce, don't dup
            return
        # Moderately similar + an LLM to judge -> possibly a contradiction/update.
        if self._use_llm and best is not None and best_sim >= _SIM_LOW:
            try:
                verdict = self.extractor.judge(content, best["content"])
            except Exception:
                verdict = "unrelated"
            if verdict == "same":
                self.touch(best["id"])
                return
            if verdict == "contradicts":
                self.supersede(best["id"],
                               MemoryItem(content=content, kind=ItemKind.FACT, scope=scope))
                return
        self.upsert(MemoryItem(content=content, kind=ItemKind.FACT, scope=scope))

    def upsert(self, item: MemoryItem) -> None:
        emb = item.embedding or self._embed(item.content)
        with self._lock:
            self._db.execute(
                """INSERT OR REPLACE INTO items
                   (id, content, kind, scope, importance, created_at, last_accessed,
                    access_count, valid_from, superseded_by, archived, embedding)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item.id, item.content, _kind(item.kind), item.scope, item.importance,
                 item.created_at, item.last_accessed, item.access_count,
                 item.valid_from, item.superseded_by, 0, json.dumps(emb)))
            self._db.commit()

    def supersede(self, old_id: str, new_item: MemoryItem) -> None:
        """Temporal update: write the new item as current and retire the old one
        (kept for history, archived out of the hot set)."""
        new_item.valid_from = time.time()
        self.upsert(new_item)
        with self._lock:
            self._db.execute(
                "UPDATE items SET superseded_by=?, archived=1 WHERE id=?",
                (new_item.id, old_id))
            self._db.commit()

    # --- read ---------------------------------------------------------------
    def search(self, query: str, scope=None, k: int = 20) -> list[RetrievalCandidate]:
        emb = self._embed(query)
        scored = sorted(
            ((_cosine(emb, json.loads(r["embedding"] or "[]")), r) for r in self._current_rows(scope)),
            key=lambda x: x[0], reverse=True)
        out = []
        for rank, (sim, r) in enumerate(scored[:k]):
            out.append(RetrievalCandidate(
                ref_id=r["id"], content=r["content"], source=Source.VECTOR,
                scope=r["scope"], rank=rank, raw_score=float(sim),
                importance=float(r["importance"] or 0.5),
                created_at=float(r["created_at"] or 0.0),
                token_estimate=max(1, len(r["content"] or "") // 4)))
        return out

    def find_similar(self, item: MemoryItem, threshold: float = 0.9) -> list[MemoryItem]:
        emb = item.embedding or self._embed(item.content)
        return [_row_to_item(r) for r in self._current_rows(item.scope)
                if _cosine(emb, json.loads(r["embedding"] or "[]")) >= threshold]

    def touch(self, item_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE items SET last_accessed=?, access_count=access_count+1, "
                "importance=MIN(1.0, importance+0.05) WHERE id=?",
                (time.time(), item_id))
            self._db.commit()

    def archive(self, item_id: str) -> None:
        with self._lock:
            self._db.execute("UPDATE items SET archived=1 WHERE id=?", (item_id,))
            self._db.commit()

    # --- consolidation helpers ---------------------------------------------
    def decay(self, half_life_days: float = 30.0, cold_threshold: float = 0.15) -> int:
        """Archive items whose effective weight (importance x recency) falls
        below cold_threshold. They stay in the table (re-derivable), just out of
        the hot search set. Returns the count archived."""
        now = time.time()
        archived = 0
        for r in self._current_rows(None):
            rec = recency_weight(now - float(r["last_accessed"] or now), half_life_days)
            if float(r["importance"] or 0.0) * rec < cold_threshold:
                self.archive(r["id"])
                archived += 1
        return archived

    def count_current(self, scope=None) -> int:
        return len(self._current_rows(scope))

    # --- internals ----------------------------------------------------------
    def _current_rows(self, scope):
        with self._lock:
            if scope is None:
                return self._db.execute(
                    "SELECT * FROM items WHERE superseded_by IS NULL AND archived=0").fetchall()
            return self._db.execute(
                "SELECT * FROM items WHERE superseded_by IS NULL AND archived=0 AND scope IS ?",
                (scope,)).fetchall()

    def _nearest(self, emb, scope):
        best, best_sim = None, -1.0
        for r in self._current_rows(scope):
            sim = _cosine(emb, json.loads(r["embedding"] or "[]"))
            if sim > best_sim:
                best, best_sim = r, sim
        return best, best_sim


# --- module helpers ---------------------------------------------------------
def _tokens(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _hash_embed(text, dim):
    """Deterministic bag-of-tokens embedding (stable across processes via md5)."""
    vec = [0.0] * dim
    for tok in _tokens(text):
        vec[int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % dim] += 1.0
    return _normalize(vec)


def _normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def _cosine(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(a[i] * b[i] for i in range(n))  # inputs are L2-normalised


def _kind(k):
    return getattr(k, "value", k) if k is not None else "fact"


def _row_to_item(r):
    return MemoryItem(
        id=r["id"], content=r["content"], scope=r["scope"],
        importance=float(r["importance"] or 0.5),
        created_at=float(r["created_at"] or 0.0),
        last_accessed=float(r["last_accessed"] or 0.0),
        access_count=int(r["access_count"] or 0),
        valid_from=float(r["valid_from"] or 0.0),
        superseded_by=r["superseded_by"])
