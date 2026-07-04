"""Router — picks a backend model per query, scope-aware.

Rules, in order:
  1. Sensitive scope  -> force an on-box model (local, else echo). NEVER a
     frontier/subscription model — sensitive memory must not leave the machine.
  2. Hard question    -> the strongest configured model.
  3. Otherwise        -> the general model.
Always returns something reachable, falling back to the offline echo model.
improvement/optimizer.py will later learn rules into policy.routing_rules, which
take precedence for the non-sensitive path.
"""
from __future__ import annotations

from memory.schema import ContextBundle

_HARD_HINTS = ("why", "how", "design", "analyze", "analyse", "explain", "prove",
               "debug", "compare", "plan", "architect", "refactor", "optimize")
_SENSITIVE_HINTS = ("private", "sensitive", "health", "medical", "finance", "personal")


class Router:
    def __init__(self, registry, policy, sensitive_scopes=None):
        self.registry = registry
        self.policy = policy
        self.sensitive_scopes = set(sensitive_scopes or ())

    def pick(self, query: str, ctx: ContextBundle, scope: str | None = None):
        # 1. Privacy first: a sensitive scope stays on-box, full stop.
        if self._is_sensitive(scope):
            return self._reachable_local()

        # 2/3. Difficulty-based routing (learned rules win if present).
        intent = self._classify(query)
        name = (self.policy.routing_rules or {}).get(intent) or self.registry.default_name(intent)
        model = self.registry.get(name)
        if model is None or not _reachable(model):
            model = self._first_reachable() or self.registry.fallback()
        return model

    # --- classification -----------------------------------------------------
    def _is_sensitive(self, scope: str | None) -> bool:
        if not scope:
            return False
        if scope in self.sensitive_scopes:
            return True
        s = scope.lower()
        return any(t in s for t in _SENSITIVE_HINTS)

    def _classify(self, query: str) -> str:
        q = (query or "").lower()
        if len(query or "") > 400 or any(h in q for h in _HARD_HINTS):
            return "hard_reasoning"
        return "general"

    # --- selection ----------------------------------------------------------
    def _reachable_local(self):
        """A reachable on-box model for sensitive scopes: the configured private
        default, then any local model, then echo. NEVER a frontier model — that
        is the privacy guarantee."""
        name = self.registry.default_name("private")
        for n in ([name] if name else []) + self.registry.names():
            m = self.registry.get(n)
            if m is not None and _is_local(m) and _reachable(m):
                return m
        return self.registry.get("echo")  # on-box last resort, never frontier

    def _first_reachable(self):
        for n in self.registry.names():
            m = self.registry.get(n)
            if _reachable(m):
                return m
        return None


def _reachable(model) -> bool:
    probe = getattr(model, "available", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:
            return False
    return True  # no availability probe => assume usable


def _is_local(model) -> bool:
    return bool(getattr(model, "is_local", False))
