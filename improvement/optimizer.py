"""Prompt / routing optimizer — learns better routing from feedback.

Phase-3 cut: a legible, dependency-free heuristic — aggregate feedback scores
per model and, if one reliably wins (with enough samples), propose routing the
default intents to it. Proposals are candidate Policy objects (the live one is
never mutated in place) handed to governance for guardrail gating, snapshot, and
audit before they take effect.

Upgrade path: swap `propose` for a DSPy **GEPA** loop that evolves prompt +
routing instructions from natural-language feedback on execution traces.
"""
from __future__ import annotations

from collections import defaultdict

from core.policy import Policy


class Optimizer:
    def __init__(self, *, min_samples: int = 5):
        self.min_samples = min_samples

    def propose(self, policy: Policy, feedback_log) -> Policy | None:
        """Return a candidate new Policy, or None if there isn't enough signal
        or nothing would change."""
        stats: dict = defaultdict(lambda: [0.0, 0])
        for s in feedback_log or []:
            m, sc = s.get("model"), s.get("score")
            if m and sc is not None:
                stats[m][0] += sc
                stats[m][1] += 1
        scored = {m: tot / n for m, (tot, n) in stats.items() if n >= self.min_samples}
        if not scored:
            return None
        best = max(scored, key=scored.get)

        new_rules = dict(policy.routing_rules)
        changed = 0
        for intent in ("general", "hard_reasoning"):
            if new_rules.get(intent) != best:
                new_rules[intent] = best
                changed += 1
        if changed == 0:
            return None
        return Policy(version=policy.version + 1, routing_rules=new_rules,
                      prompt_templates=dict(policy.prompt_templates))

    def apply(self, current: Policy, proposal: Policy, *, guardrails=None,
              versioning=None, audit=None) -> Policy | None:
        """Gate a proposal through governance: guardrail check -> snapshot ->
        audit. Returns the approved Policy, or None if denied."""
        if proposal is None:
            return None
        changed = sum(1 for k in proposal.routing_rules
                      if current.routing_rules.get(k) != proposal.routing_rules.get(k))
        if guardrails is not None and not guardrails.allow("policy_update", {"changed": changed}):
            if audit is not None:
                audit.record("policy_update", current.snapshot(), None,
                             f"DENIED by guardrails ({changed} rule changes)")
            return None
        version_id = (versioning.snapshot("pre-policy-update", current.snapshot())
                      if versioning is not None else None)
        if audit is not None:
            audit.record("policy_update", current.snapshot(), proposal.snapshot(),
                         f"optimizer proposal v{proposal.version}; rollback_id={version_id}")
        return proposal
