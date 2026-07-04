"""Consolidation — the background 'sleep' pass. Your real differentiator.

Runs when idle or on a nightly schedule. Turns a growing pile of raw logs into
memory that gets *wiser* over time instead of merely bigger. None of this is on
the hot path — it can be slow and use a cheap or local model.

Each stage is independent and can ship one at a time. Start with `summarize`
and `decay`; they give the most value for the least code.
"""
from __future__ import annotations


class Consolidator:
    def __init__(self, *, episodic, semantic, graph, summarizer=None,
                 half_life_days: float = 30.0, cold_threshold: float = 0.15):
        self.episodic = episodic
        self.semantic = semantic
        self.graph = graph
        self.summarizer = summarizer      # a cheap/local model is fine here
        self.half_life_days = half_life_days
        self.cold_threshold = cold_threshold

    def run(self) -> None:
        """Full pass. Implement each stage:

          summarize : cluster recent episodes and compress them into
                      higher-level notes (session -> weekly rollups,
                      hierarchically). Store rollups as ItemKind.SUMMARY so
                      retrieval can surface a whole week in a few tokens.

          promote   : mine the episodic log for durable facts that live
                      extraction missed and upsert them to semantic memory.
                      This is your safety net for the stingy write path.

          reconcile : find contradicting/duplicate items and entities; supersede
                      stale facts, merge duplicate entities (graph.merge_entities).
                      Temporal reasoning lives here — resolve "was true then vs
                      true now" rather than letting both sit in the index.

          decay     : recompute effective importance from access stats; archive
                      items below cold_threshold out of the hot vector index
                      (semantic.archive). They stay in episodic — never deleted,
                      always re-derivable.

          re_embed  : if the embedding model changed, re-embed affected items so
                      the vector space stays internally consistent.
        """
        raise NotImplementedError("Implement consolidation stages; see ARCHITECTURE.md (Consolidation)")
