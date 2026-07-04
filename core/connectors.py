"""Connectors — read your real world: git, calendar, email.

Local-first and private by design. Every connector here reads from something on
your machine (a git repo, an .ics file, an mbox), so it works offline, needs no
credentials, and leaks nothing. They're exposed to the agent as read-only,
`unattended` tools, so routines can use them safely. Anything that needs the
network + credentials (CalDAV, IMAP) is a documented extension on top of these.
"""
from __future__ import annotations

import calendar as _cal
import json
import mailbox
import os
import subprocess
import time
import urllib.request


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


def _looks_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _fetch_url_text(url: str):
    """Guarded GET for a published .ics URL (Google/Outlook secret address).
    Reuses the web tools' SSRF guard so it can't be pointed at private hosts."""
    from core.tools import _UA, _safe_url
    ok, why = _safe_url(url)
    if not ok:
        return None, f"(blocked: {why})"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read(1_000_000).decode("utf-8", errors="ignore"), None
    except Exception as e:
        return None, f"(error: {e})"


def calendar_upcoming(path: str, days: int = 7, now: float | None = None) -> str:
    if not path:
        return "(no calendar — set calendar_file or pass a path/URL)"
    if _looks_url(path):                       # networked calendar (published .ics)
        text, err = _fetch_url_text(path)
        if err:
            return err
    elif not os.path.exists(path):
        return "(no calendar file — set calendar_file or pass a path/URL)"
    else:
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


# --- GitHub (networked, read-only) ------------------------------------------
def _parse_github_commits(json_text: str) -> list:
    try:
        data = json.loads(json_text)
    except Exception:
        return []
    out = []
    for c in (data if isinstance(data, list) else []):
        sha = (c.get("sha") or "")[:7]
        commit = c.get("commit") or {}
        msg = (commit.get("message") or "").splitlines()[0] if commit.get("message") else ""
        author = (commit.get("author") or {}).get("name") or ""
        if sha:
            out.append((sha, msg, author))
    return out


def github_recent(repo: str, token: str | None = None, n: int = 10) -> str:
    """Recent commits on a GitHub repo via the REST API. Public repos need no
    token; a token (config github_token) unlocks private repos + rate limit."""
    repo = (repo or "").strip().strip("/")
    if "/" not in repo:
        return "(set github_repo as owner/name, or pass repo=owner/name)"
    url = f"https://api.github.com/repos/{repo}/commits?per_page={int(n)}"
    headers = {"User-Agent": "agi-layer", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(1_000_000).decode("utf-8", errors="ignore")
    except Exception as e:
        return f"(error: {e})"
    commits = _parse_github_commits(body)
    if not commits:
        return "(no commits, or the repo isn't accessible)"
    return "\n".join(f"{sha} {msg}" + (f"  — {a}" if a else "")
                     for sha, msg, a in commits[:int(n)])


# --- IMAP email (networked, read-only) --------------------------------------
def _fmt_headers(frm: str, subject: str, date: str) -> str:
    return f"{date or '?'} · {frm or '?'} — {subject or '(no subject)'}"


def imap_recent(host: str, user: str, password: str, n: int = 10,
                use_ssl: bool = True, mailbox_name: str = "INBOX") -> str:
    """Recent message headers over IMAP. Config-gated; credentials stay on your
    machine. Read-only (BODY.PEEK — never marks anything seen)."""
    if not (host and user and password):
        return "(imap not configured — set imap_host / imap_user / imap_password)"
    try:
        import email
        import imaplib
        from email.header import decode_header, make_header
    except Exception as e:
        return f"(error: {e})"
    try:
        M = imaplib.IMAP4_SSL(host) if use_ssl else imaplib.IMAP4(host)
        M.login(user, password)
        M.select(mailbox_name, readonly=True)
        _, data = M.search(None, "ALL")
        ids = (data[0].split() if data and data[0] else [])[-int(n):]
        rows = []
        for i in reversed(ids):
            _, msg_data = M.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            raw = msg_data[0][1].decode("utf-8", errors="ignore") if msg_data and msg_data[0] else ""
            m = email.message_from_string(raw)
            rows.append(_fmt_headers(str(make_header(decode_header(m.get("From", "")))),
                                     str(make_header(decode_header(m.get("Subject", "")))),
                                     m.get("Date", "")))
        M.logout()
        return "\n".join(rows) or "(mailbox empty)"
    except Exception as e:
        return f"(error: {e})"


# --- health check -----------------------------------------------------------
def connector_status(config: dict | None) -> dict:
    config = config or {}
    st = {}
    repo = config.get("git_repo") or "."
    inside = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    st["git"] = f"ok ({repo})" if inside.strip() == "true" else f"not a git repo ({repo})"
    cal = config.get("calendar_file")
    if cal and _looks_url(cal):
        st["calendar"] = f"ok (url: {cal})"
    elif cal and os.path.exists(cal):
        st["calendar"] = f"ok ({cal})"
    else:
        st["calendar"] = "not configured"
    mbx = config.get("mailbox_file")
    st["email"] = f"ok ({mbx})" if mbx and os.path.exists(mbx) else "not configured"
    gh = config.get("github_repo")
    st["github"] = f"ok ({gh})" if gh and "/" in gh else "not configured"
    st["imap"] = ("ok (" + str(config.get("imap_host")) + ")"
                  if config.get("imap_host") and config.get("imap_user")
                  and config.get("imap_password") else "not configured")
    return st
