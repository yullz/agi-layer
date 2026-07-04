"""Episodic store — append-only raw log of every turn (SQLite).

Source of truth: everything else can be re-derived from this, so it is
append-only and never hard-deleted. Backs the keyword and recency retrievers.
Uses SQLite FTS5 for keyword search when available, falling back to a tokenised
LIKE match otherwise.
"""
from __future__ import annotations

import json
import sqlite3
import threading

from memory.schema import Episode, RetrievalCandidate, Role, Source


class EpisodicStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        # check_same_thread=False: the write path may ingest on a background
        # thread; all access is serialised through self._lock.
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._fts = False
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    ts REAL NOT NULL,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    model TEXT,
                    tool_calls TEXT,
                    latency_ms INTEGER,
                    feedback REAL,
                    scope TEXT
                )
                """
            )
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(ts)")
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_episodes_scope ON episodes(scope)")
            try:
                self._db.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts "
                    "USING fts5(id UNINDEXED, content, scope UNINDEXED)"
                )
                self._fts = True
            except sqlite3.OperationalError:
                self._fts = False  # FTS5 not compiled in -> LIKE fallback
            self._db.commit()

    # --- write --------------------------------------------------------------
    def append(self, episode: Episode) -> None:
        role = episode.role.value if isinstance(episode.role, Role) else str(episode.role)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO episodes "
                "(id, ts, session_id, role, content, model, tool_calls, latency_ms, feedback, scope) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (episode.id, episode.ts, episode.session_id, role, episode.content,
                 episode.model, json.dumps(episode.tool_calls or []),
                 episode.latency_ms, episode.feedback, episode.scope),
            )
            if self._fts:
                self._db.execute(
                    "INSERT INTO episodes_fts (id, content, scope) VALUES (?,?,?)",
                    (episode.id, episode.content or "", episode.scope or ""),
                )
            self._db.commit()

    # --- read ---------------------------------------------------------------
    def recent(self, session_id: str, n: int = 12) -> list[Episode]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM episodes WHERE session_id=? ORDER BY ts DESC LIMIT ?",
                (session_id, n),
            ).fetchall()
        return [self._row_to_episode(r) for r in reversed(rows)]

    def search(self, terms: str, scope: str | None = None, limit: int = 20) -> list[RetrievalCandidate]:
        """Keyword search (FTS5 or LIKE). Empty `terms` => most-recent-first,
        which is how the recency retriever uses it. Returns RetrievalCandidates
        tagged KEYWORD (or RECENCY for the empty-terms case)."""
        terms = (terms or "").strip()
        with self._lock:
            if not terms:
                source = Source.RECENCY
                if scope:
                    rows = self._db.execute(
                        "SELECT * FROM episodes WHERE scope IS ? ORDER BY ts DESC LIMIT ?",
                        (scope, limit),
                    ).fetchall()
                else:
                    rows = self._db.execute(
                        "SELECT * FROM episodes ORDER BY ts DESC LIMIT ?", (limit,)
                    ).fetchall()
            else:
                source = Source.KEYWORD
                rows = self._keyword_rows(terms, scope, limit)
        return [self._row_to_candidate(r, source, rank) for rank, r in enumerate(rows)]

    def _keyword_rows(self, terms: str, scope: str | None, limit: int):
        tokens = _fts_tokens(terms)
        if self._fts and tokens:
            try:
                match = " OR ".join(tokens)
                if scope:
                    return self._db.execute(
                        "SELECT e.* FROM episodes_fts f JOIN episodes e ON e.id=f.id "
                        "WHERE episodes_fts MATCH ? AND e.scope IS ? ORDER BY rank LIMIT ?",
                        (match, scope, limit),
                    ).fetchall()
                return self._db.execute(
                    "SELECT e.* FROM episodes_fts f JOIN episodes e ON e.id=f.id "
                    "WHERE episodes_fts MATCH ? ORDER BY rank LIMIT ?",
                    (match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                pass  # fall through to LIKE
        tokens = tokens or [terms]
        clause = " OR ".join(["content LIKE ?"] * len(tokens))
        params: list = [f"%{t}%" for t in tokens]
        sql = f"SELECT * FROM episodes WHERE ({clause})"
        if scope:
            sql += " AND scope IS ?"
            params.append(scope)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        return self._db.execute(sql, params).fetchall()

    def iter_since(self, ts: float):
        """Walk new episodes — used by consolidation."""
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM episodes WHERE ts > ? ORDER BY ts ASC", (ts,)
            ).fetchall()
        for r in rows:
            yield self._row_to_episode(r)

    # --- helpers ------------------------------------------------------------
    def _row_to_episode(self, r) -> Episode:
        return Episode(
            id=r["id"], ts=r["ts"], session_id=r["session_id"],
            role=_role(r["role"]), content=r["content"], scope=r["scope"],
            model=r["model"], tool_calls=json.loads(r["tool_calls"] or "[]"),
            latency_ms=r["latency_ms"], feedback=r["feedback"],
        )

    def _row_to_candidate(self, r, source: Source, rank: int) -> RetrievalCandidate:
        content = r["content"] or ""
        return RetrievalCandidate(
            ref_id=r["id"], content=content, source=source, scope=r["scope"],
            rank=rank, raw_score=1.0, created_at=r["ts"],
            token_estimate=max(1, len(content) // 4),
        )


def _role(value) -> Role:
    try:
        return Role(value)
    except Exception:
        return Role.USER


def _fts_tokens(terms: str) -> list[str]:
    """Sanitise free text into safe FTS5 tokens (drop punctuation/operators)."""
    out = []
    for tok in terms.replace('"', " ").split():
        clean = "".join(ch for ch in tok if ch.isalnum())
        if clean:
            out.append(clean)
    return out
