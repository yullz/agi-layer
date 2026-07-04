"""Write path — turn raw exchanges into durable, de-duplicated memory.

Two phases:
  append_raw : synchronous, microseconds — never lose the raw turn.
  ingest     : off the hot path — extract candidate facts, then for each one
               decide insert / supersede / reinforce against existing memory
               *before* writing. This dedup/reconcile step is what keeps memory
               from rotting into a pile of contradictions, and it is the single
               most-skipped step in naive memory systems.
"""
from __future__ import annotations

from core.log import log
from memory.schema import Episode, MemoryItem, Role, Turn


class WritePipeline:
    def __init__(self, *, episodic, semantic, graph, extractor=None, queue=None):
        self.episodic = episodic
        self.semantic = semantic
        self.graph = graph
        self.extractor = extractor   # LLM/rules that emit candidate MemoryItems
        self.queue = queue           # background queue (thread/task) for ingest

    def append_raw(self, turn: Turn) -> None:
        """Persist the raw exchange immediately. Cheap and lossless — this must
        never be skipped or deferred, it is your source of truth."""
        self.episodic.append(Episode(
            session_id=turn.session_id, role=Role.USER,
            content=turn.user_input, scope=turn.scope, ts=turn.ts,
        ))
        self.episodic.append(Episode(
            session_id=turn.session_id, role=Role.ASSISTANT,
            content=turn.assistant_reply, scope=turn.scope,
            model=turn.model, ts=turn.ts,
        ))

    def enqueue_ingest(self, turn: Turn) -> None:
        """Hand ingest to the background worker so the turn returns fast. Falls
        back to synchronous ingest if no queue is wired yet."""
        if self.queue is None:
            self.ingest(turn)
        else:
            self.queue.put(turn)

    def ingest(self, turn: Turn) -> None:
        """Extract durable memory from a turn and merge it in.

        Implement each step:

          1. candidates = self.extractor.extract(turn)   # -> list[MemoryItem]
             Ask: is there anything here worth remembering next week? Most turns
             yield zero. Be stingy — for memory, precision beats recall. A wrong
             "fact" is worse than a missing one because it will be retrieved
             confidently later.

          2. For each candidate, RECONCILE before writing:
               similar = self.semantic.find_similar(candidate)
               - no match            -> upsert as new
               - same fact, restated -> bump the existing item's importance and
                                        drop the candidate (no duplicate row)
               - contradicts a fact  -> supersede: set old.superseded_by, then
                                        write the new item with valid_from=now
                                        (keep the old one — history matters)

          3. Update the GRAPH: upsert entities named in the candidate and the
             relations between them. Relations are temporal too — supersede,
             don't delete, when something changes.

          4. Record any demonstrated workflow/preference to the procedural
             store so it can be replayed when the task recurs.
        """
        # Hybrid write: hand the exchange to the semantic store (Mem0), which
        # does extraction + dedup/supersede internally — the reconcile-on-write
        # the naive path skips. Graph/procedural updates land in a later phase.
        # Best-effort: a failure here must not lose the appended raw episode.
        try:
            add_turn = getattr(self.semantic, "add_turn", None)
            if callable(add_turn):
                add_turn(turn.user_input, turn.assistant_reply, scope=turn.scope)
        except Exception:
            log.warning("semantic ingest failed (raw episode kept)", exc_info=True)

        # Populate the knowledge graph: extract entities and link relations.
        try:
            self._update_graph(turn)
        except Exception:
            log.warning("graph update failed", exc_info=True)

    def _update_graph(self, turn: Turn) -> None:
        if not hasattr(self.graph, "get_or_create_entity"):
            return
        text = f"{turn.user_input} {turn.assistant_reply}"

        # Typed relations via the LLM extractor when available (subject-predicate
        # -object) — real multi-hop structure, not just co-occurrence.
        ex = self.extractor
        if (ex is not None and hasattr(ex, "extract_relations")
                and getattr(ex, "available", lambda: False)()):
            try:
                triples = ex.extract_relations(text)
            except Exception:
                triples = None
            if triples:
                for s, p, o in triples:
                    sid = self.graph.get_or_create_entity(s, scope=turn.scope)
                    oid = self.graph.get_or_create_entity(o, scope=turn.scope)
                    self.graph.relate(sid, oid, p, scope=turn.scope)
                return

        # Heuristic co-occurrence fallback.
        from memory.extract import extract_entities
        names = extract_entities(text)
        if len(names) < 2:
            return
        ids = [self.graph.get_or_create_entity(n, scope=turn.scope) for n in names]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                self.graph.relate(ids[i], ids[j], "mentioned_with", scope=turn.scope)
