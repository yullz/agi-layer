"""Guardrails — the bounded action space and approval gates.

A system that self-modifies AND acts on your behalf needs limits:
  - which actions run unattended vs require confirmation
  - rate/impact ceilings on self-updates
  - a sandbox requirement for self-authored skills before registration

FAIL CLOSED. Until real policy checks exist, `allow` denies every action and
`requires_confirmation` demands confirmation for everything not explicitly
whitelisted. A guardrail that raised (the previous behaviour) would crash the
caller instead of protecting it; one that returned True by default would wave
through exactly the self-modifications it exists to gate. Deny-by-default is the
only safe placeholder.
"""
from __future__ import annotations


class Guardrails:
    def __init__(self, *, unattended: set[str] | None = None):
        # Actions explicitly allowed to run without confirmation. Empty = none.
        self.unattended = set(unattended or ())

    def allow(self, action: str, payload=None) -> bool:
        # Deny by default. Populate real rate/impact/sandbox checks here.
        return False

    def requires_confirmation(self, action: str) -> bool:
        # Everything needs confirmation unless explicitly marked unattended.
        return action not in self.unattended
