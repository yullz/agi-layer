"""Prompt / routing optimizer — learns better prompts and routing from feedback.

Runs a DSPy-style optimization loop over accumulated (input, context, output,
feedback) tuples to propose improved prompt templates and routing rules.
Proposals are versioned and gated by governance before they take effect.
"""
from __future__ import annotations


class Optimizer:
    def propose(self, policy, feedback_log):
        """Return a candidate new Policy. Never mutate the live policy in
        place — hand the proposal to governance for snapshot + approval."""
        raise NotImplementedError("Implement the DSPy loop; see ARCHITECTURE.md (Self-improvement)")
