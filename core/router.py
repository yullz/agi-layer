"""Router — picks a backend model per query."""
from __future__ import annotations

from memory.schema import ContextBundle


class Router:
    def __init__(self, registry, policy):
        self.registry = registry
        self.policy = policy

    def pick(self, query: str, ctx: ContextBundle):
        """Choose a model from the registry for this query.

        Decision inputs: query difficulty/length, whether the task is
        privacy-sensitive (scope tells you -> force a local model), cost
        ceiling, required capabilities (vision, long context, tools), and the
        learned routing policy (improvement/optimizer.py updates it).

        Returns a model adapter from models/registry.py.
        """
        raise NotImplementedError("Implement model selection; see ARCHITECTURE.md (Router)")
