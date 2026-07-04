"""Procedural store — learned 'how to do X for this user' + workflows.

Distinct from the routing policy (core/policy.py). Holds reusable task recipes
and demonstrated preferences the context builder can inject when a matching task
recurs. Phase-1 placeholder: constructible and safe — `lookup` returns None (no
learned recipe yet). Back it with a small SQLite table when you start recording
demonstrated workflows.
"""
from __future__ import annotations


class ProceduralStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def record(self, task: str, recipe: dict, scope: str | None = None) -> None:
        return

    def lookup(self, task: str, scope: str | None = None) -> dict | None:
        return None
