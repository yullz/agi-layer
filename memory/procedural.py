"""Procedural store — learned 'how to do X for this user' + workflows.

Distinct from the routing policy (that lives in core/policy.py). This holds
reusable task recipes and demonstrated preferences the context builder can
inject when a matching task recurs.
"""
from __future__ import annotations


class ProceduralStore:
    def __init__(self, db_path):
        self.db_path = db_path
        raise NotImplementedError("Init the procedural store; see ARCHITECTURE.md (Stores)")

    def record(self, task: str, recipe: dict, scope: str | None = None) -> None:
        raise NotImplementedError

    def lookup(self, task: str, scope: str | None = None) -> dict | None:
        raise NotImplementedError
