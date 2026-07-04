"""Consolidation — the background 'sleep' pass. The differentiator.

Turns a growing pile of raw episodes into memory that gets wiser, not just
bigger. Off the hot path; safe to run nightly or on idle. This first cut ships
the two highest-value stages — **summarize** + a **watermark** so each run only
processes new episodes — with a graceful extractive fallback when no summarizer
model is wired. promote / reconcile / decay / re_embed are follow-ups.
"""
from __future__ import annotations

import json
from collections import defaultdict

from memory.schema import ItemKind, MemoryItem


class Consolidator:
    def __init__(self, *, episodic, semantic, graph, summarizer=None,
                 half_life_days: float = 30.0, cold_threshold: float = 0.15,
                 min_cluster: int = 3):
        self.episodic = episodic
        self.semantic = semantic
        self.graph = graph
        self.summarizer = summarizer      # a cheap/local model is fine here
        self.half_life_days = half_life_days
        self.cold_threshold = cold_threshold
        self.min_cluster = min_cluster
        self._state_path = f"{getattr(episodic, 'db_path', 'episodic.db')}.consolidation.json"

    def run(self) -> dict:
        """Summarize new episodes (grouped by scope) into SUMMARY memory items,
        advancing a watermark so each run only sees new episodes. Returns a small
        report. Never raises on a single failed group."""
        since = self._last_ts()
        episodes = list(self.episodic.iter_since(since))
        if not episodes:
            return {"new_episodes": 0, "scopes": 0, "summaries": 0}

        by_scope: dict = defaultdict(list)
        for ep in episodes:
            by_scope[ep.scope].append(ep)

        summaries, max_ts = 0, since
        for scope, eps in by_scope.items():
            max_ts = max(max_ts, max(e.ts for e in eps))
            if len(eps) < self.min_cluster:
                continue
            text = self._summarize(eps)
            if not text:
                continue
            try:
                self.semantic.upsert(MemoryItem(content=text, kind=ItemKind.SUMMARY, scope=scope))
                summaries += 1
            except Exception:
                pass

        promoted = self._promote(episodes)
        archived = self._decay()
        self._save_ts(max_ts)
        return {"new_episodes": len(episodes), "scopes": len(by_scope),
                "summaries": summaries, "promoted": promoted, "archived": archived}

    def _promote(self, episodes) -> int:
        """Mine new user episodes for durable facts live extraction missed and
        reconcile them into semantic memory. Reconcile dedups, so re-mining is
        safe. No-op when the store doesn't support add_turn."""
        add_turn = getattr(self.semantic, "add_turn", None)
        if not callable(add_turn):
            return 0
        n = 0
        for ep in episodes:
            if _role(ep) != "user" or not ep.content:
                continue
            try:
                add_turn(ep.content, "", scope=ep.scope)
                n += 1
            except Exception:
                pass
        return n

    def _decay(self) -> int:
        """Recompute effective importance and archive cold items. No-op when the
        store doesn't support decay (e.g. Mem0 manages its own)."""
        decay = getattr(self.semantic, "decay", None)
        if not callable(decay):
            return 0
        try:
            return decay(self.half_life_days, self.cold_threshold)
        except Exception:
            return 0

    # --- summarization ------------------------------------------------------
    def _summarize(self, eps) -> str:
        if self.summarizer is not None:
            joined = "\n".join(f"{_role(e)}: {e.content}" for e in eps if e.content)
            try:
                out = self.summarizer.generate([
                    {"role": "system", "content":
                     "Summarize these turns into durable, factual notes about the "
                     "user (facts, preferences, projects). Be concise."},
                    {"role": "user", "content": joined},
                ])
                if out and out.strip():
                    return out.strip()
            except Exception:
                pass
        # Extractive fallback (no summarizer / model unreachable): keep the
        # user's statements, truncated.
        user_lines = [e.content for e in eps if _role(e) == "user" and e.content]
        return ("Session rollup: " + " | ".join(user_lines[:8]))[:800] if user_lines else ""

    # --- watermark ----------------------------------------------------------
    def _last_ts(self) -> float:
        try:
            with open(self._state_path) as f:
                return float(json.load(f).get("last_ts", 0.0))
        except Exception:
            return 0.0

    def _save_ts(self, ts: float) -> None:
        try:
            with open(self._state_path, "w") as f:
                json.dump({"last_ts": ts}, f)
        except Exception:
            pass


def _role(ep) -> str:
    r = getattr(ep, "role", None)
    return getattr(r, "value", r) if r is not None else ""
