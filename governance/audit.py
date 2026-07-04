"""Audit log — an append-only record of every self-modification.

Anything the system changes about *itself* (policy update, new skill,
fine-tune swap, memory bulk edit) is logged here with before/after and a
reason. This is your black box: when behaviour drifts, read this first.
"""
from __future__ import annotations


class Audit:
    def record(self, kind: str, before, after, reason: str) -> None:
        raise NotImplementedError("Append to the audit log; see ARCHITECTURE.md (Governance)")
