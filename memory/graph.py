"""Knowledge graph — entities and typed relations about the user's world.

Enables multi-hop retrieval ('what tools do I use across projects') that
vector search alone cannot. Two SQLite tables (nodes, edges) is enough to
start; move to an embedded graph engine only if traversals get heavy.
"""
from __future__ import annotations

from memory.schema import Entity, Relation, RetrievalCandidate


class GraphStore:
    def __init__(self, graph_dir):
        self.graph_dir = graph_dir
        raise NotImplementedError("Init graph tables; see ARCHITECTURE.md (Stores)")

    def upsert_entity(self, entity: Entity) -> None:
        raise NotImplementedError

    def upsert_relation(self, relation: Relation) -> None:
        raise NotImplementedError

    def neighbors(self, entity_names: list[str], scope: str | None = None,
                  hops: int = 2) -> list[RetrievalCandidate]:
        """Traverse from the named entities and return connected facts as
        RetrievalCandidate objects (source=GRAPH)."""
        raise NotImplementedError

    def merge_entities(self, keep_id: str, drop_id: str) -> None:
        """Used by consolidation to dedupe entities."""
        raise NotImplementedError
