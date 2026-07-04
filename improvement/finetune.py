"""Local fine-tuning — periodic LoRA jobs on accumulated interactions.

The heaviest, slowest improvement mechanism, and real self-improvement of a
component: periodically distill the episodic log into a training set and
LoRA-tune a local model so it gets better at *your* recurring tasks.
Schedule it rarely (weekly/monthly); never on the hot path.
"""
from __future__ import annotations


class FineTuner:
    def run(self) -> None:
        raise NotImplementedError("Build the LoRA pipeline; see ARCHITECTURE.md (Self-improvement)")
