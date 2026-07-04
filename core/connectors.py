"""Connectors — read your real world: git, calendar, email.

Local-first and private by design. Every connector here reads from something on
your machine (a git repo, an .ics file, an mbox), so it works offline, needs no
credentials, and leaks nothing. They're exposed to the agent as read-only,
`unattended` tools, so routines can use them safely. Anything that needs the
network + credentials (CalDAV, IMAP) is a documented extension on top of these.
"""
from __future__ import annotations

import calendar as _cal
import mailbox
import os
import subprocess
import time


# --- git --------------------------------------------------------------------
def _run_git(path, args, timeout: float = 10.0) -> str:
    try:
        r = subprocess.run(["git", "-C", str(path or "."), *args],
                           capture_output=True, text=True, timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return f"(error: {e})"


def git_log(path: str = ".", n: int = 10) -> str:
    out = _run_git(path, ["log", f"-n{int(n)}", "--oneline"])
    return out or "(no commits)"


def git_status(path: str = ".") -> str:
    out = _run_git(path, ["status", "--short", "--branch"])
    return out or "(clean working tree)"


# --- calendar (.ics) --------------------------------------------------------
def _ics_dt(val: str):
    """Parse an iCalendar DTSTART value to a UTC epoch. Datetimes without an
    explicit zone are treated as UTC (a documented approximation)."""
    v = (val or "").strip()
    utc = v.endswith("Z")
    v = v[:-1] if utc else v
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return float(_cal.timegm(time.strptime(v, fmt)))
        except Exception:
            continue
    return None


def _parse_ics(text: str) -> list:
    events, cur = [], None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            key = key.split(";", 1)[0].upper()
            if key == "SUMMARY":
                cur["summary"] = val.strip()
            elif key == "DTSTART":
                cur["start"] = _ics_dt(val)
    return events


def calendar_upcoming(path: str, days: int = 7, now: float | None = None) -> str:
    if not path or not os.path.exists(path):
        return "(no calendar file — set calendar_file or pass a path)"
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as e:
        return f"(error: {e})"
    now = time.time() if now is None else now
    horizon = now + int(days) * 86400
    up = [(ev["start"], ev.get("summary", "(untitled)")) for ev in _parse_ics(text)
          if ev.get("start") is not None and now - 60 <= ev["start"] <= horizon]
    up.sort()
    if not up:
        return f"(no events in the next {days} days)"
    return "\n".join(f"{_fmt_ts(st)} — {s}" for st, s in up)


def _fmt_ts(ts: float) -> str:
    return time.strftime("%a %d %b %H:%M", time.gmtime(ts))


# --- email (mbox) -----------------------------------------------------------
def email_recent(path: str, n: int = 10) -> str:
    if not path or not os.path.exists(path):
        return "(no mailbox — set mailbox_file or pass a path)"
    try:
        box = mailbox.mbox(path)
        keys = list(box.keys())
    except Exception as e:
        return f"(error: {e})"
    rows = []
    for key in keys[-int(n):]:
        try:
            m = box[key]
        except Exception:
            continue
        rows.append(f"{m.get('Date', '?')} · {m.get('From', '?')} — "
                    f"{m.get('Subject', '(no subject)')}")
    return "\n".join(reversed(rows)) or "(mailbox empty)"


# --- health check -----------------------------------------------------------
def connector_status(config: dict | None) -> dict:
    config = config or {}
    st = {}
    repo = config.get("git_repo") or "."
    inside = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    st["git"] = f"ok ({repo})" if inside.strip() == "true" else f"not a git repo ({repo})"
    cal = config.get("calendar_file")
    st["calendar"] = f"ok ({cal})" if cal and os.path.exists(cal) else "not configured"
    mbx = config.get("mailbox_file")
    st["email"] = f"ok ({mbx})" if mbx and os.path.exists(mbx) else "not configured"
    return st
