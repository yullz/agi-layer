"""Versioning — snapshot and rollback for policy and memory.

Version the system's own policy and periodically snapshot memory so a bad
self-update or a corrupt consolidation run can be reverted. Pairs with
audit.py: every change is both logged and reversible.
"""
from __future__ import annotations


class Versioning:
    def snapshot(self, label: str) -> str:
        """Snapshot current policy + memory state; return a version id."""
        raise NotImplementedError

    def rollback(self, version_id: str) -> None:
        raise NotImplementedError("Implement rollback; see ARCHITECTURE.md (Governance)")
