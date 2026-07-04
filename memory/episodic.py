"""Episodic store — append-only raw log of every turn (SQLite).

Source of truth. Everything else can be re-derived from this, so it is
append-only and never hard-deleted. Cold memory items also land here once
evicted from the hot vector index.
"""
from __future__ import annotations

from memory.schema import Episode, RetrievalCandidate


class EpisodicStore:
    def __init__(self, db_path):
        self.db_path = db_path
        # TODO: open SQLite, create table if missing
        # (id, ts, session_id, role, content, model, tool_calls json,
        #  latency_ms, feedback, scope) + an FTS5 index over content.
        raise NotImplementedError("Init SQLite; see ARCHITECTURE.md (Stores)")

    def append(self, episode: Episode) -> None:
        raise NotImplementedError

    def recent(self, session_id: str, n: int = 12) -> list[Episode]:
        raise NotImplementedError

    def search(self, terms: str, scope: str | None = None, limit: int = 20) -> list[RetrievalCandidate]:
        """Keyword search (SQLite FTS5). Empty `terms` = most-recent-first,
        which is how the recency retriever uses it. Return RetrievalCandidate
        objects (source=KEYWORD or RECENCY) so the pipeline can fuse them."""
        raise NotImplementedError

    def iter_since(self, ts: float):
        """Walk new episodes — used by consolidation."""
        raise NotImplementedError
