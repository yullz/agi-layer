"""Routines — saved tasks the agent runs on demand or on a schedule.

A routine is a named (task, scope) the agent executes UNATTENDED: no confirm
callback, so any tool flagged `unattended=False` (write_file, run_shell) is
denied fail-closed. Automations are therefore safe by construction — a routine
can read, search, browse, compute, and remember, but never silently writes files
or runs shell commands. Persisted as JSON so they survive restarts.

Scheduling is dependency-free and stored per routine:
  - `every_minutes: N`  -> run every N minutes;
  - `at: "HH:MM"`       -> run once a day at that local time.
A minute-tick scheduler calls `run_due()`, which fires whatever is due, records
`last_run`/`last_result`, and advances the next-run bookkeeping.
"""
from __future__ import annotations

import json
import os
import time

from core.profile import day_key as _day_key
from core.profile import now_hhmm as _now_hhmm


class Routines:
    def __init__(self, path, agent, tz=None):
        self.path = str(path)
        self.agent = agent
        self.tz = tz            # user's tzinfo; None -> machine local time
        self._items = self._load()

    def set_tz(self, tz) -> None:
        """Apply the user's timezone (from onboarding/profile) so daily 'at
        HH:MM' routines fire at their local wall-clock, not the machine's."""
        self.tz = tz

    # --- CRUD ---------------------------------------------------------------
    def add(self, name: str, task: str, scope: str | None = None,
            every_minutes: int | None = None, at: str | None = None) -> dict:
        it = self._items.get(name, {})
        it.update({"task": task, "scope": scope})
        self._items[name] = it
        if every_minutes is not None or at is not None:
            self.schedule(name, every_minutes=every_minutes, at=at)
        else:
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

    def schedule(self, name: str, every_minutes: int | None = None,
                 at: str | None = None, now: float | None = None) -> bool:
        """Attach (or clear) a schedule. every_minutes and at are mutually
        exclusive; pass both None to unschedule."""
        it = self._items.get(name)
        if it is None:
            return False
        it.pop("every_minutes", None)
        it.pop("at", None)
        it.pop("next_run", None)
        it.pop("_last_day", None)
        if every_minutes:
            it["every_minutes"] = int(every_minutes)
            it["next_run"] = (time.time() if now is None else now) + int(every_minutes) * 60
        elif at:
            it["at"] = _norm_hhmm(at)
        self._save()
        return True

    def unschedule(self, name: str) -> bool:
        return self.schedule(name)

    # --- run ----------------------------------------------------------------
    def run(self, name: str) -> dict:
        item = self._items.get(name)
        if item is None:
            return {"status": "no-such-routine", "name": name}
        # UNATTENDED: confirm=None -> gated tools are denied fail-closed.
        result = self.agent.run(item["task"], scope=item.get("scope"), confirm=None)
        return {"status": "ran", "name": name, **result}

    def run_due(self, now: float | None = None) -> list:
        """Run every scheduled routine that's due. Returns [{name, answer}]."""
        now = time.time() if now is None else now
        fired = []
        for name, it in list(self._items.items()):
            if not self._is_due(it, now):
                continue
            res = self.run(name)
            it["last_run"] = now
            it["last_result"] = (res.get("answer") or "")[:500]
            if it.get("every_minutes"):
                it["next_run"] = now + int(it["every_minutes"]) * 60
            elif it.get("at"):
                it["_last_day"] = _day_key(self.tz, now)
            fired.append({"name": name, "answer": res.get("answer")})
        if fired:
            self._save()
        return fired

    def _is_due(self, it: dict, now: float) -> bool:
        if it.get("every_minutes"):
            nr = it.get("next_run")
            return nr is None or now >= nr
        at = it.get("at")
        if at:
            # Evaluate "at HH:MM" against the user's timezone, and reset the
            # once-a-day guard at their local midnight (not the machine's).
            current = _now_hhmm(self.tz, now)
            return current >= at and it.get("_last_day") != _day_key(self.tz, now)
        return False

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


def _norm_hhmm(s: str) -> str:
    """Coerce '8:5' / '08:05' -> '08:05'; falls back to the raw string."""
    try:
        h, m = (s or "").strip().split(":", 1)
        return f"{int(h):02d}:{int(m):02d}"
    except Exception:
        return (s or "").strip()


def describe_schedule(it: dict) -> str:
    """Human-readable schedule for the CLI (empty if none)."""
    if it.get("every_minutes"):
        return f"every {it['every_minutes']}m"
    if it.get("at"):
        return f"daily at {it['at']}"
    return ""
