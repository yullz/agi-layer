"""Feedback capture — explicit and implicit signals for the improvement loop."""
from __future__ import annotations

from core.session import Session


class Feedback:
    def observe(self, session: Session, reply: str) -> None:
        """Capture signal on the turn just completed.

        Explicit: thumbs / ratings the user gives.
        Implicit: did the user immediately rephrase or correct? abandon?
        latency? These become training signal for optimizer.py and importance
        boosts for the memories that led to a good turn.
        """
        raise NotImplementedError("Record feedback; see ARCHITECTURE.md (Self-improvement)")
