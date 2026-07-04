"""Versioning — snapshot and rollback for policy (and, later, memory).

Version the system's own policy so a bad self-update can be reverted. Pairs with
audit.py: every change is both logged and reversible. Snapshots are JSON files;
`rollback` returns the stored state for the caller to re-apply.
"""
from __future__ import annotations

import json
import os
import time


class Versioning:
    def __init__(self, store_dir):
        self.dir = str(store_dir)
        os.makedirs(self.dir, exist_ok=True)

    def snapshot(self, label: str, state=None) -> str:
        """Persist `state` under a new version id and return the id."""
        version_id = f"{int(time.time() * 1000)}"
        payload = {"id": version_id, "ts": time.time(), "label": label, "state": state}
        try:
            with open(os.path.join(self.dir, f"{version_id}.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f, default=str)
        except Exception:
            pass
        return version_id

    def rollback(self, version_id: str):
        """Return the snapshotted state for a version id (caller re-applies it)."""
        try:
            with open(os.path.join(self.dir, f"{version_id}.json"), encoding="utf-8") as f:
                return json.load(f).get("state")
        except Exception:
            return None

    def list(self) -> list[str]:
        try:
            return sorted(x[:-5] for x in os.listdir(self.dir) if x.endswith(".json"))
        except Exception:
            return []
