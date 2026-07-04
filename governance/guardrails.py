"""Guardrails — the bounded action space and approval gates.

A system that self-modifies AND acts on your behalf needs limits:
  - which actions run unattended vs require confirmation
  - rate/impact ceilings on self-updates
  - a sandbox requirement for self-authored skills before registration
Every self-modification proposal passes through here before taking effect.
"""
from __future__ import annotations


class Guardrails:
    def allow(self, action: str, payload) -> bool:
        raise NotImplementedError("Implement policy checks; see ARCHITECTURE.md (Governance)")

    def requires_confirmation(self, action: str) -> bool:
        raise NotImplementedError
