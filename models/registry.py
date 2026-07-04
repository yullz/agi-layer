"""Model registry — available backends and their capabilities/costs.

Loads model definitions from config/models.yaml (passed in as a dict) and
constructs one adapter per entry via injected factories. The router asks it for
a model by name or by capability/cost. Construction never raises on a single
bad/unavailable backend — it skips it — so the registry can't become a boot
wall, and an offline `echo` backend is always guaranteed to exist.
"""
from __future__ import annotations

_COST_RANK = {"free": 0, "low": 1, "medium": 2, "high": 3}


class ModelRegistry:
    def __init__(self, config: dict, frontier_factory, local_factory, echo_factory=None):
        config = config or {}
        self._defaults: dict = dict(config.get("defaults", {}))
        self._meta: dict = {}      # name -> config entry
        self._adapters: dict = {}  # name -> adapter instance

        if echo_factory is None:
            from models.echo import EchoModel
            echo_factory = EchoModel

        for entry in config.get("models", []):
            name = entry.get("name")
            if not name:
                continue
            kind = entry.get("adapter")
            try:
                if kind == "frontier":
                    adapter = frontier_factory(name, provider=entry.get("provider"))
                elif kind == "local":
                    adapter = local_factory(
                        name, endpoint=entry.get("endpoint", "http://localhost:11434"))
                elif kind == "echo":
                    adapter = echo_factory(name)
                else:
                    continue
            except Exception:
                # A backend that can't even be constructed is simply unavailable.
                continue
            self._meta[name] = entry
            self._adapters[name] = adapter

        # Guarantee an always-available offline fallback.
        if "echo" not in self._adapters:
            self._adapters["echo"] = echo_factory("echo")
            self._meta["echo"] = {"name": "echo", "adapter": "echo",
                                  "capabilities": [], "cost": "free", "privacy": "local"}
        self._defaults.setdefault("fallback", "echo")

    # --- lookup -------------------------------------------------------------
    def get(self, name: str | None):
        return self._adapters.get(name) if name else None

    def default_name(self, intent: str) -> str | None:
        return self._defaults.get(intent)

    def fallback(self):
        return (self._adapters.get(self._defaults.get("fallback", "echo"))
                or self._adapters.get("echo"))

    def names(self) -> list[str]:
        return list(self._adapters)

    def candidates(self, *, needs: set | None = None, max_cost: float | None = None):
        """Return adapters matching capability/cost constraints, for the router."""
        out = []
        for name, entry in self._meta.items():
            caps = set(entry.get("capabilities", []))
            if needs and not needs.issubset(caps):
                continue
            if max_cost is not None and _COST_RANK.get(entry.get("cost", "high"), 3) > max_cost:
                continue
            out.append(self._adapters[name])
        return out
