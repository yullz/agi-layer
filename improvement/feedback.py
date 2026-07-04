"""Feedback capture — explicit and implicit signals for the improvement loop."""
from __future__ import annotations

from core.session import Session


class Feedback:
    def __init__(self):
        # In-memory ring of recent signals. Phase 3 persists these and feeds
        # them to the optimizer + importance boosts for memories that helped.
        self.signals: list[dict] = []

    def observe(self, session: Session, reply: str) -> None:
        """Capture signal on the turn just completed.

        Explicit: thumbs / ratings the user gives. Implicit: did the user
        rephrase or correct? abandon? latency? Phase 1 records a lightweight
        marker; the miner + optimizer read it later. Best-effort — never raises.
        """
        try:
            self.signals.append({
                "session_id": getattr(session, "session_id", None),
                "scope": getattr(session, "active_scope", None),
                "reply_len": len(reply or ""),
            })
        except Exception:
            pass
