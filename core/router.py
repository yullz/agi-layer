"""Router — picks a backend model per query.

Phase-1 policy is a small, legible rule set: hard questions -> the strongest
model, everything else -> the general model, with a hard guarantee that we
return something reachable (falling back to the offline echo model when no key
or local runtime is up). improvement/optimizer.py will later learn better rules
and write them into policy.routing_rules, which take precedence here.

(Privacy routing — sensitive scope -> forced local — lands once scope is
threaded into pick(); today pick() only sees the query + retrieved context.)
"""
from __future__ import annotations

from memory.schema import ContextBundle

# Cheap heuristic: these hint the query wants deeper reasoning.
_HARD_HINTS = ("why", "how", "design", "analyze", "analyse", "explain", "prove",
               "debug", "compare", "plan", "architect", "refactor", "optimize")


class Router:
    def __init__(self, registry, policy):
        self.registry = registry
        self.policy = policy

    def pick(self, query: str, ctx: ContextBundle):
        intent = self._classify(query)
        # Learned rules win if present, else the config defaults.
        name = (self.policy.routing_rules or {}).get(intent) or self.registry.default_name(intent)
        model = self.registry.get(name)

        # Only route to a model we can actually reach right now.
        if model is None or not _reachable(model):
            model = self._first_reachable() or self.registry.fallback()
        return model

    def _classify(self, query: str) -> str:
        q = (query or "").lower()
        if len(query or "") > 400 or any(h in q for h in _HARD_HINTS):
            return "hard_reasoning"
        return "general"

    def _first_reachable(self):
        for name in self.registry.names():
            m = self.registry.get(name)
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
