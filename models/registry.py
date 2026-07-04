"""Model registry — available backends and their capabilities/costs."""
from __future__ import annotations


class ModelRegistry:
    """Loads models from config/models.yaml and exposes adapters.

    Each entry: name, adapter (frontier|local), context window, cost,
    capabilities (vision, tools, long_context), privacy tier.
    """
    def __init__(self, config: dict, frontier_factory, local_factory):
        raise NotImplementedError("Build the registry from config; see ARCHITECTURE.md (Model layer)")

    def get(self, name: str):
        raise NotImplementedError

    def candidates(self, *, needs: set[str] | None = None, max_cost: float | None = None):
        """Return adapters matching capability/cost constraints, for the router."""
        raise NotImplementedError
