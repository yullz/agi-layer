"""Feedback capture — explicit and implicit signals for the improvement loop."""
from __future__ import annotations

import json
import time

from core.session import Session


class Feedback:
    def __init__(self, path=None):
        self.path = str(path) if path else None
        self.signals: list[dict] = []

    def observe(self, session: Session, reply: str, *, model: str | None = None,
                score: float | None = None) -> None:
        """Record a turn's signal — the model used, reply length, scope, and an
        optional explicit score. Best-effort; never raises."""
        try:
            sig = {
                "ts": time.time(),
                "session_id": getattr(session, "session_id", None),
                "scope": getattr(session, "active_scope", None),
                "model": model,
                "reply_len": len(reply or ""),
                "score": score,
            }
            self.signals.append(sig)
            self._persist(sig)
        except Exception:
            pass

    def rate(self, session_id: str, score: float) -> None:
        """Attach an explicit score to the most recent signal for a session."""
        for sig in reversed(self.signals):
            if sig.get("session_id") == session_id:
                sig["score"] = float(score)
                self._persist({**sig, "explicit": True})
                return

    def recent(self, n: int = 200) -> list[dict]:
        return self.signals[-n:]

    def by_model(self) -> dict:
        """Average score + sample count per model — the optimizer's raw signal."""
        agg: dict = {}
        for s in self.signals:
            m, sc = s.get("model"), s.get("score")
            if m is None or sc is None:
                continue
            a = agg.setdefault(m, {"sum": 0.0, "n": 0})
            a["sum"] += sc
            a["n"] += 1
        return {m: {"avg": a["sum"] / a["n"], "n": a["n"]} for m, a in agg.items() if a["n"]}

    def _persist(self, sig: dict) -> None:
        if not self.path:
            return
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sig, default=str) + "\n")
        except Exception:
            pass
