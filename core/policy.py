"""Routing / decision policy — the part that improves over time.

Holds the current routing rules and prompt templates. Treated as data and
versioned by governance/versioning.py so a bad self-update can be rolled
back. improvement/optimizer.py proposes updates; guardrails gate them.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Policy:
    version: int = 1
    routing_rules: dict = field(default_factory=dict)
    prompt_templates: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        return {
            "version": self.version,
            "routing_rules": dict(self.routing_rules),
            "prompt_templates": dict(self.prompt_templates),
        }
