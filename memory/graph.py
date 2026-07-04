"""Knowledge graph — entities and typed temporal relations (SQLite).

Enables multi-hop retrieval ('what tools do I use across projects') that vector
search alone cannot. Two tables (entities, relations); traversal is a bounded
BFS returning connected facts as GRAPH candidates. Relations are temporal:
superseded ones (superseded_by set) are skipped, so history is preserved without
polluting current retrieval.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

from memory.schema import Entity, Relation, RetrievalCandidate, Source


class GraphStore:
    def __init__(self, graph_dir):
        self.graph_dir = str(graph_dir)
        os.makedirs(self.graph_dir, exist_ok=True)
        self.db_path = os.path.join(self.graph_dir, "graph.db")
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS entities "
                "(id TEXT PRIMARY KEY, name TEXT, type TEXT, scope TEXT, attributes TEXT)")
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS relations "
                "(id TEXT PRIMARY KEY, src TEXT, dst TEXT, type TEXT, scope TEXT, "
                "valid_from REAL, superseded_by TEXT)")
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_ent_name ON entities(name)")
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src)")
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst)")
            self._db.commit()

    def upsert_entity(self, entity: Entity) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO entities (id, name, type, scope, attributes) "
                "VALUES (?,?,?,?,?)",
                (entity.id, entity.name, entity.type, entity.scope,
                 json.dumps(entity.attributes or {})))
            self._db.commit()

    def upsert_relation(self, relation: Relation) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO relations "
                "(id, src, dst, type, scope, valid_from, superseded_by) VALUES (?,?,?,?,?,?,?)",
                (relation.id, relation.src, relation.dst, relation.type,
                 relation.scope, relation.valid_from, relation.superseded_by))
            self._db.commit()

    def get_or_create_entity(self, name: str, type: str = "", scope: str | None = None) -> str:
        """Return the id of an existing (name, scope) entity or create one, so
        the graph stays deduped by name+scope and relations stay stable."""
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM entities WHERE name=? AND scope IS ?", (name, scope)).fetchone()
            if row:
                return row["id"]
            ent = Entity(name=name, type=type, scope=scope)
            self._db.execute(
                "INSERT INTO entities (id, name, type, scope, attributes) VALUES (?,?,?,?,?)",
                (ent.id, ent.name, ent.type, ent.scope, json.dumps({})))
            self._db.commit()
            return ent.id

    def relate(self, src_id: str, dst_id: str, type: str, scope: str | None = None) -> None:
        """Create a current relation if an identical one doesn't already exist."""
        with self._lock:
            exists = self._db.execute(
                "SELECT 1 FROM relations WHERE src=? AND dst=? AND type=? AND scope IS ? "
                "AND superseded_by IS NULL", (src_id, dst_id, type, scope)).fetchone()
            if exists:
                return
            rel = Relation(src=src_id, dst=dst_id, type=type, scope=scope)
            self._db.execute(
                "INSERT INTO relations (id, src, dst, type, scope, valid_from, superseded_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (rel.id, rel.src, rel.dst, rel.type, rel.scope, rel.valid_from, rel.superseded_by))
            self._db.commit()

    def neighbors(self, entity_names: list[str], scope: str | None = None,
                  hops: int = 2) -> list[RetrievalCandidate]:
        """Traverse from the named entities and return connected (current) facts
        as GRAPH candidates."""
        if not entity_names:
            return []
        with self._lock:
            seed = self._find_entities(entity_names, scope)
            if not seed:
                return []
            names = {r["id"]: r["name"] for r in seed}
            frontier = set(names)
            visited = set(frontier)
            rels: dict = {}
            for _ in range(max(1, hops)):
                if not frontier:
                    break
                marks = ",".join("?" * len(frontier))
                params = list(frontier) + list(frontier)
                sql = (f"SELECT * FROM relations WHERE superseded_by IS NULL AND "
                       f"(src IN ({marks}) OR dst IN ({marks}))")
                if scope:
                    sql += " AND scope IS ?"
                    params.append(scope)
                nxt = set()
                for rel in self._db.execute(sql, params).fetchall():
                    rels[rel["id"]] = rel
                    for eid in (rel["src"], rel["dst"]):
                        if eid not in names:
                            row = self._db.execute(
                                "SELECT name FROM entities WHERE id=?", (eid,)).fetchone()
                            names[eid] = row["name"] if row else eid
                        if eid not in visited:
                            visited.add(eid)
                            nxt.add(eid)
                frontier = nxt
        out = []
        for rel in rels.values():
            content = (f"{names.get(rel['src'], rel['src'])} "
                       f"—{rel['type']}→ {names.get(rel['dst'], rel['dst'])}")
            out.append(RetrievalCandidate(
                ref_id=rel["id"], content=content, source=Source.GRAPH,
                scope=rel["scope"], token_estimate=max(1, len(content) // 4)))
        return out

    def merge_entities(self, keep_id: str, drop_id: str) -> None:
        """Repoint drop_id's relations onto keep_id and delete the duplicate."""
        with self._lock:
            self._db.execute("UPDATE relations SET src=? WHERE src=?", (keep_id, drop_id))
            self._db.execute("UPDATE relations SET dst=? WHERE dst=?", (keep_id, drop_id))
            self._db.execute("DELETE FROM entities WHERE id=?", (drop_id,))
            self._db.commit()

    def _find_entities(self, names: list[str], scope: str | None):
        out = []
        for nm in names:
            if scope:
                out.extend(self._db.execute(
                    "SELECT * FROM entities WHERE name=? AND scope IS ?", (nm, scope)).fetchall())
            else:
                out.extend(self._db.execute(
                    "SELECT * FROM entities WHERE name=?", (nm,)).fetchall())
        return out
