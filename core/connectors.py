"""Connectors — read *and act on* your real world: git, calendar, email, GitHub.

Two tiers live here, and the distinction is the security posture:

  - Local, read-only, `unattended` (safe for automations): git_log/git_status,
    calendar_upcoming (local .ics), email_recent (mbox). No credentials, offline,
    nothing leaves the machine.
  - Networked and/or write, some credentialed: github_* reads, imap_recent,
    plus the WRITE actions github_create_issue / calendar_add_event / smtp_send.
    The write actions are registered as GATED tools (unattended=False) in
    core/tools.py — the agent denies them without a confirm callback, so
    automations can't silently create issues, edit calendars, or send mail.

Outbound requests go through the web tools' SSRF guard + redirect-revalidating
opener; credentials stay in local config and never appear in returned strings.
"""
from __future__ import annotations

import calendar as _cal
import hashlib
import re
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
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
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
                cur["summary"] = _ics_unescape(val.strip())
            elif key == "DTSTART":
                cur["start"] = _ics_dt(val)
    return events


def _ics_unescape(text: str) -> str:
    """Reverse RFC 5545 TEXT escaping (\\, \\; \\, ) for display/round-trip."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append({"n": "\n", "N": "\n"}.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _looks_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _fetch_url_text(url: str):
    """Guarded GET for a published .ics URL (Google/Outlook secret address).
    Reuses the web tools' SSRF guard + redirect-revalidating opener."""
    from core.tools import _UA, _safe_url, _safe_urlopen
    ok, why = _safe_url(url)
    if not ok:
        return None, f"(blocked: {why})"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with _safe_urlopen(req, timeout=15) as r:
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


# --- GitHub issues / PRs (read) + create issue (write) ----------------------
def _gh_get(url: str, token: str | None) -> str:
    from core.tools import _safe_urlopen
    headers = {"User-Agent": "agi-layer", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with _safe_urlopen(req, timeout=15) as r:
        return r.read(1_000_000).decode("utf-8", errors="ignore")


def _gh_page_size(n: int) -> int:
    """GitHub caps per_page at 100. For /issues we over-fetch (it interleaves
    PRs we drop client-side) so we still return up to n real issues."""
    return max(1, min(100, int(n)))


def _parse_github_items(json_text: str, issues_only: bool = False) -> list:
    try:
        data = json.loads(json_text)
    except Exception:
        return []
    out = []
    for it in (data if isinstance(data, list) else []):
        # The /issues endpoint also returns PRs; a PR carries a `pull_request`
        # object (which may be empty), so test presence, not truthiness.
        if issues_only and it.get("pull_request") is not None:
            continue
        out.append((it.get("number"), (it.get("title") or "").strip(),
                    (it.get("user") or {}).get("login") or ""))
    return out


def _fmt_items(items, n: int) -> str:
    return "\n".join(f"#{num} {title}" + (f"  — {who}" if who else "")
                     for num, title, who in items[:int(n)])


def github_issues(repo: str, token: str | None = None, n: int = 10) -> str:
    repo = (repo or "").strip().strip("/")
    if "/" not in repo:
        return "(set github_repo as owner/name, or pass repo=owner/name)"
    # /issues interleaves PRs; over-fetch a full page so that after dropping PRs
    # we can still surface up to n real issues.
    try:
        body = _gh_get(f"https://api.github.com/repos/{repo}/issues?state=open"
                       f"&per_page={_gh_page_size(100)}", token)
    except Exception as e:
        return f"(error: {e})"
    items = _parse_github_items(body, issues_only=True)
    return _fmt_items(items, n) or "(no open issues, or the repo isn't accessible)"


def github_prs(repo: str, token: str | None = None, n: int = 10) -> str:
    repo = (repo or "").strip().strip("/")
    if "/" not in repo:
        return "(set github_repo as owner/name, or pass repo=owner/name)"
    try:
        body = _gh_get(f"https://api.github.com/repos/{repo}/pulls?state=open"
                       f"&per_page={_gh_page_size(n)}", token)
    except Exception as e:
        return f"(error: {e})"
    items = _parse_github_items(body)
    return _fmt_items(items, n) or "(no open pull requests, or the repo isn't accessible)"


def _build_github_issue_request(repo: str, title: str, body: str, token: str):
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {"User-Agent": "agi-layer", "Accept": "application/vnd.github+json",
               "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps({"title": title, "body": body or ""}).encode("utf-8")
    return url, headers, data


def github_create_issue(repo: str, title: str, body: str = "",
                        token: str | None = None) -> str:
    repo = (repo or "").strip().strip("/")
    if "/" not in repo:
        return "(set github_repo as owner/name, or pass repo=owner/name)"
    if not token:
        return "(creating an issue needs github_token)"
    if not title:
        return "(need a title)"
    from core.tools import _safe_urlopen
    url, headers, data = _build_github_issue_request(repo, title, body, token)
    try:
        req = urllib.request.Request(url, headers=headers, data=data, method="POST")
        with _safe_urlopen(req, timeout=15) as r:
            resp = json.loads(r.read(1_000_000).decode("utf-8", errors="ignore"))
        return f"created issue #{resp.get('number')}: {resp.get('html_url', '')}".strip()
    except Exception as e:
        return f"(error: {e})"


# --- calendar (write) -------------------------------------------------------
def _parse_when(when):
    """Accept an epoch or a few common date/time strings; return a UTC epoch."""
    if isinstance(when, (int, float)):
        return float(when)
    s = str(when or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y-%m-%d"):
        try:
            return float(_cal.timegm(time.strptime(s, fmt)))
        except Exception:
            continue
    return None


def _ics_escape(text: str) -> str:
    """RFC 5545 TEXT escaping + collapse ALL line breaks/whitespace to spaces
    (a raw CR/LF/VT would split the content line on read and corrupt the event)."""
    text = " ".join(str(text).split())
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def _ics_event_block(uid: str, title: str, start_epoch: float, end_epoch: float) -> str:
    def fmt(ts):
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(ts))
    return ("BEGIN:VEVENT\n"
            f"UID:{uid}\n"
            f"SUMMARY:{_ics_escape(title)}\n"
            f"DTSTART:{fmt(start_epoch)}\n"
            f"DTEND:{fmt(end_epoch)}\n"
            "END:VEVENT\n")


def _ics_insert(text: str, block: str) -> str:
    """Insert an event block into an existing calendar. If the file has a proper
    VCALENDAR envelope, splice the block before the LAST `END:VCALENDAR` *line*
    (an unanchored replace could hit that string inside a property value).
    Otherwise (empty / wrapper-less file) wrap everything in a fresh envelope."""
    lines = text.splitlines()
    has_begin = any(ln.strip() == "BEGIN:VCALENDAR" for ln in lines)
    end_idx = next((i for i in range(len(lines) - 1, -1, -1)
                    if lines[i].strip() == "END:VCALENDAR"), None)
    if has_begin and end_idx is not None:
        lines[end_idx:end_idx] = block.rstrip("\n").split("\n")
        return "\n".join(lines) + "\n"
    inner = text.strip()
    inner = (inner + "\n") if inner else ""
    return "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//agi-layer//EN\n" + inner + block + "END:VCALENDAR\n"


def calendar_add_event(path: str, title: str, start, duration_min: int = 60) -> str:
    if not path:
        return "(no calendar file — set calendar_file or pass a path)"
    if _looks_url(path):
        return "(can't write to a calendar URL — use a local .ics path)"
    if not title:
        return "(need a title)"
    st = _parse_when(start)
    if st is None:
        return "(couldn't parse the start time — try 'YYYY-MM-DD HH:MM')"
    en = st + int(duration_min) * 60
    # UID keys on title+start+end so a different duration is a distinct event.
    uid = ("agi-" + hashlib.md5(f"{title}{st}{en}".encode("utf-8")).hexdigest()[:16]
           + "@agi-layer")
    block = _ics_event_block(uid, title, st, en)
    try:
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        if f"UID:{uid}" in text:                       # idempotent — don't duplicate
            return f"'{title}' is already on the calendar at {_fmt_ts(st)}"
        text = _ics_insert(text, block)
        # RFC 5545 §3.1 requires CRLF line endings.
        text = re.sub(r"\r?\n", "\r\n", text)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return f"added '{title}' at {_fmt_ts(st)}"
    except Exception as e:
        return f"(error: {e})"


# --- email (send via SMTP) --------------------------------------------------
def _build_email(from_addr: str, to_addr: str, subject: str, body: str):
    from email.mime.text import MIMEText
    msg = MIMEText(body or "", _charset="utf-8")
    msg["From"] = from_addr or ""
    msg["To"] = to_addr or ""
    msg["Subject"] = subject or ""
    return msg


def smtp_send(host: str, user: str, password: str, to_addr: str, subject: str,
              body: str, from_addr: str | None = None, port: int = 587,
              use_tls: bool = True) -> str:
    if not (host and user and password):
        return "(smtp not configured — set smtp_host / smtp_user / smtp_password)"
    if not to_addr:
        return "(need a recipient — pass to=…)"
    from_addr = from_addr or user
    msg = _build_email(from_addr, to_addr, subject, body)
    try:
        import smtplib
        port = int(port)
        implicit = (port == 465)                       # 465 = TLS-on-connect (SMTP_SSL)
        s = (smtplib.SMTP_SSL(host, port, timeout=20) if implicit
             else smtplib.SMTP(host, port, timeout=20))
        try:
            if not implicit and use_tls:               # 587 = STARTTLS upgrade
                s.starttls()
            s.login(user, password)
            s.sendmail(from_addr, [to_addr], msg.as_string())
        finally:
            try:
                s.quit()                               # cleanup must never mask the real error
            except Exception:
                try:
                    s.close()
                except Exception:
                    pass
        return f"sent to {to_addr}"
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
    st["smtp"] = ("ok (" + str(config.get("smtp_host")) + ")"
                  if config.get("smtp_host") and config.get("smtp_user")
                  and config.get("smtp_password") else "not configured")
    return st
