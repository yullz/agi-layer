"""Guardrails — the bounded action space and approval gates.

FAIL CLOSED by default: unknown actions are denied. A small allow-list opens
specific, bounded actions (e.g. a routing-policy update within an impact
ceiling) so the governed improvement loop can run without waving the whole gate
open. Self-authored skills, fine-tune swaps, and bulk memory edits stay denied
until explicitly implemented and added here.
"""
from __future__ import annotations


class Guardrails:
    def __init__(self, *, allowed_actions=None, max_policy_changes: int = 4,
                 unattended=None):
        self.allowed_actions = set(allowed_actions or {"policy_update"})
        self.max_policy_changes = max_policy_changes
        self.unattended = set(unattended or ())

    def allow(self, action: str, payload=None) -> bool:
        if action not in self.allowed_actions:
            return False  # fail closed for anything not explicitly opened
        if action == "policy_update":
            changed = (payload or {}).get("changed", 10 ** 9)
            return changed <= self.max_policy_changes
        return True

    def requires_confirmation(self, action: str) -> bool:
        return action not in self.unattended
