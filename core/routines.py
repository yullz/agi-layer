"""Routines — saved tasks the agent runs on demand (or, later, on a schedule).

A routine is a named (task, scope) the agent executes UNATTENDED: no confirm
callback, so any tool flagged `unattended=False` (write_file, run_shell) is
denied fail-closed. Automations are therefore safe by construction — a routine
can read, search, compute, and summarise, but never silently writes files or
runs shell commands. Persisted as JSON so they survive restarts.
"""
from __future__ import annotations

import json
import os


class Routines:
    def __init__(self, path, agent):
        self.path = str(path)
        self.agent = agent
        self._items = self._load()

    def add(self, name: str, task: str, scope: str | None = None) -> dict:
        self._items[name] = {"task": task, "scope": scope}
        self._save()
        return self._items[name]

    def remove(self, name: str) -> bool:
        if name in self._items:
            del self._items[name]
            self._save()
            return True
        return False

    def list(self) -> dict:
        return dict(self._items)

    def run(self, name: str) -> dict:
        item = self._items.get(name)
        if item is None:
            return {"status": "no-such-routine", "name": name}
        # UNATTENDED: confirm=None -> gated tools are denied fail-closed.
        result = self.agent.run(item["task"], scope=item.get("scope"), confirm=None)
        return {"status": "ran", "name": name, **result}

    # --- persistence --------------------------------------------------------
    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._items, f, indent=2)
        except Exception:
            pass
