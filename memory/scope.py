"""Scope + privacy helpers, shared by the router and the memory layer.

A memory's `scope` is a project/domain tag. `None` means global (applies
everywhere — identity/seed facts). Retrieval in scope S returns S + global; a
sensitive scope must never leave the machine.
"""
from __future__ import annotations

_SENSITIVE_HINTS = (
    "private", "sensitive", "health", "medical", "therapy", "diary", "journal",
    "finance", "financial", "bank", "money", "legal", "hr", "ssn", "personal",
)


def is_sensitive_scope(scope, extra=()) -> bool:
    """True if a scope's memory must stay on-box. Global/None scope is NOT
    sensitive by default (it holds identity facts, not secrets); write secrets
    under an explicitly sensitive scope."""
    if not scope:
        return False
    if scope in (extra or ()):
        return True
    s = scope.lower()
    return any(t in s for t in _SENSITIVE_HINTS)
