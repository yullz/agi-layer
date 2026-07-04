"""Knowledge graph — entities and typed relations about the user's world.

Enables multi-hop retrieval ('what tools do I use across projects') that vector
search alone cannot. Phase-1 placeholder: constructible and safe (never raises),
but not yet a real graph — `neighbors` returns nothing, so graph retrieval
simply contributes no candidates and the pipeline runs on vector + keyword +
recency. Implement the two SQLite tables (nodes, edges) to light up multi-hop.
"""
from __future__ import annotations

from memory.schema import Entity, Relation, RetrievalCandidate


class GraphStore:
    def __init__(self, graph_dir):
        self.graph_dir = str(graph_dir)

    def upsert_entity(self, entity: Entity) -> None:
        return

    def upsert_relation(self, relation: Relation) -> None:
        return

    def neighbors(self, entity_names: list[str], scope: str | None = None,
                  hops: int = 2) -> list[RetrievalCandidate]:
        return []

    def merge_entities(self, keep_id: str, drop_id: str) -> None:
        return
