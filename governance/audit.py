"""Audit log — an append-only record of every self-modification (JSONL).

Anything the system changes about *itself* (policy update, new skill, fine-tune
swap, memory bulk edit) is logged here with before/after and a reason. Your black
box: when behaviour drifts, read this first.
"""
from __future__ import annotations

import json
import os
import time


class Audit:
    def __init__(self, path):
        self.path = str(path)
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)

    def record(self, kind: str, before, after, reason: str) -> None:
        entry = {"ts": time.time(), "kind": kind, "before": before,
                 "after": after, "reason": reason}
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass

    def tail(self, n: int = 20) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as f:
                lines = f.readlines()[-n:]
            return [json.loads(x) for x in lines]
        except Exception:
            return []
