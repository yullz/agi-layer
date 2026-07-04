"""Skill registry — tools the layer can call, including self-authored ones."""
from __future__ import annotations


class Skills:
    def available(self, scope: str | None = None) -> list:
        """Return the tools usable in the current scope. Phase 1: none yet."""
        return []

    def author(self, gap_description: str):
        """When the layer hits a capability gap, generate a new tool
        (code + schema), test it in a sandbox, and register it on success.
        Voyager-style skill acquisition. Gated by governance/guardrails.
        """
        raise NotImplementedError("Implement skill authoring; see ARCHITECTURE.md (Self-improvement)")
