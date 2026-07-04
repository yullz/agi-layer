"""Tools the agent can call to actually *do* things — the hands of the layer.

Each Tool declares whether it's `unattended` (safe to run without asking — the
clock, arithmetic, reading memory/files) or not (writing files, running commands
— these need confirmation and are denied outright in automation contexts). The
agent loop enforces that and audits every call.
"""
from __future__ import annotations

import ast
import ipaddress
import operator
import os
import re
import socket
import subprocess
import time
import urllib.parse
import urllib.request


class Tool:
    def __init__(self, name, description, func, params=None, unattended=True):
        self.name = name
        self.description = description
        self.func = func
        self.params = params or {}
        self.unattended = unattended

    def spec(self):
        return {"name": self.name, "description": self.description,
                "args": list(self.params), "unattended": self.unattended}

    def run(self, args):
        return self.func(args or {})


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def add(self, tool):
        self._tools[tool.name] = tool
        return self

    def get(self, name):
        return self._tools.get(name)

    def names(self):
        return list(self._tools)

    def specs(self):
        return [t.spec() for t in self._tools.values()]


# --- built-in tools ---------------------------------------------------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.FloorDiv: operator.floordiv}


def _safe_calc(args):
    expr = str(args.get("expression", ""))

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("unsupported")

    try:
        return ev(ast.parse(expr, mode="eval").body)
    except Exception:
        return "(invalid expression)"


def _list_dir(args):
    try:
        return ", ".join(sorted(os.listdir(str(args.get("path", "."))))[:100]) or "(empty)"
    except Exception as e:
        return f"(error: {e})"


def _read_file(args):
    try:
        with open(str(args.get("path", "")), "r", encoding="utf-8", errors="ignore") as f:
            return f.read(4000)
    except Exception as e:
        return f"(error: {e})"


def _write_file(args):
    path, content = str(args.get("path", "")), str(args.get("content", ""))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"(error: {e})"


def _run_shell(args):
    try:
        r = subprocess.run(str(args.get("command", "")), shell=True,
                           capture_output=True, text=True, timeout=20)
        return (r.stdout + r.stderr)[:4000] or "(no output)"
    except Exception as e:
        return f"(error: {e})"


# --- web / browser tools ----------------------------------------------------
# Reading the public web is genuinely useful (news, docs, weather) and is a
# read-only outbound GET, so these are `unattended` — automations can use them.
# But the network is a real attack surface, so web_fetch is hardened: http/https
# only, an SSRF guard that blocks localhost/private/link-local targets (even when
# a hostname *resolves* to one), a byte cap, and a short timeout. Turn the whole
# capability off with allow_web=False if you want an air-gapped layer.
_WEB_MAX_BYTES = 400_000
_WEB_MAX_CHARS = 6_000
_UA = "Mozilla/5.0 (compatible; agi-layer/1.0)"


def _safe_url(url: str):
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return False, "unparseable url"
    if p.scheme not in ("http", "https"):
        return False, "only http/https is allowed"
    host = p.hostname or ""
    if not host:
        return False, "no host"
    if host == "localhost" or host.endswith(".local"):
        return False, "local address blocked"
    # Block private/loopback targets, resolving hostnames first (SSRF guard).
    candidates = [host]
    try:
        candidates += [sa[0] for *_, sa in socket.getaddrinfo(host, None)]
    except Exception:
        pass
    for cand in candidates:
        try:
            ip = ipaddress.ip_address(cand)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved \
                or ip.is_multicast or ip.is_unspecified:
            return False, "private/loopback address blocked"
    return True, ""


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|head|nav|footer|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")):
        html = html.replace(ent, ch)
    html = re.sub(r"[ \t\r\f]+", " ", html)
    html = re.sub(r"\n\s*\n+", "\n", html)
    return html.strip()


def _web_fetch(args):
    url = str(args.get("url", "")).strip()
    ok, why = _safe_url(url)
    if not ok:
        return f"(blocked: {why})"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            raw = r.read(_WEB_MAX_BYTES)
        text = raw.decode("utf-8", errors="ignore")
        if "html" in ctype or text.lstrip()[:1] == "<":
            text = _html_to_text(text)
        return text[:_WEB_MAX_CHARS] or "(no readable text)"
    except Exception as e:
        return f"(error: {e})"


def _parse_ddg(html: str):
    out = []
    for m in re.finditer(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html, re.S):
        href, title = m.group(1), re.sub(r"(?s)<[^>]+>", "", m.group(2)).strip()
        rel = re.search(r"uddg=([^&]+)", href)
        if rel:
            href = urllib.parse.unquote(rel.group(1))
        elif href.startswith("//"):
            href = "https:" + href
        if title and href:
            out.append((title, href))
    return out


def _web_search(args):
    q = str(args.get("query", "")).strip()
    if not q:
        return "(no query)"
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(_WEB_MAX_BYTES).decode("utf-8", errors="ignore")
    except Exception as e:
        return f"(search unavailable: {e})"
    results = _parse_ddg(html)
    if not results:
        return "(no results — the search page may have changed)"
    return "\n".join(f"{i}. {t} — {u}" for i, (t, u) in enumerate(results[:6], 1))


def _browse(args):
    """Open a URL in a real headless browser (Chromium via Playwright), let its
    JavaScript run, and return the rendered text — for pages `web_fetch` can't
    read (SPAs, infinite-scroll, JS-gated content). Same SSRF guard as fetch.

    Degrades cleanly: if Playwright (or its browser) isn't installed, or the
    launch fails, it falls back to the plain-text `web_fetch`, so the tool always
    returns something useful. Install with `pip install playwright && playwright
    install chromium`."""
    url = str(args.get("url", "")).strip()
    ok, why = _safe_url(url)
    if not ok:
        return f"(blocked: {why})"
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return _web_fetch(args)   # no Playwright -> plain fetch
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_UA)
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                text = page.inner_text("body")
            finally:
                browser.close()
        text = re.sub(r"\n\s*\n+", "\n", text or "").strip()
        return text[:_WEB_MAX_CHARS] or "(no readable text)"
    except Exception as e:
        fb = _web_fetch(args)     # launch/render failed -> best-effort fetch
        return fb if not fb.startswith("(error") else f"(error: {e})"


# --- interactive browsing ---------------------------------------------------
# A tiny action DSL so the agent can *act* on a page, not just read it. Because
# acting can log in, submit forms, or make purchases, `browse_do` is GATED
# (unattended=False): it needs confirmation and is denied in automations. Reading
# is unattended; acting is not.
_ACTION_VERBS = {"goto", "click", "fill", "type", "select", "press", "wait", "read"}


def _parse_actions(text: str) -> list:
    """One action per line: `verb target [= value]`. Blank lines and lines
    starting with # are ignored; unknown verbs are skipped."""
    actions = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, _, tail = line.partition(" ")
        verb = head.lower()
        if verb not in _ACTION_VERBS:
            continue
        rest = tail.strip()
        if verb in ("fill", "type", "select") and "=" in rest:
            target, value = (p.strip() for p in rest.split("=", 1))
        else:
            target, value = rest, ""
        actions.append({"verb": verb, "target": target, "value": value})
    return actions


def _do_action(page, act, reads):
    v, t, val = act["verb"], act["target"], act["value"]
    if v == "goto":
        page.goto(t, timeout=20000, wait_until="domcontentloaded")
    elif v == "click":
        page.click(t, timeout=8000)
    elif v in ("fill", "type"):
        page.fill(t, val, timeout=8000)
    elif v == "select":
        page.select_option(t, val, timeout=8000)
    elif v == "press":
        page.keyboard.press(t or "Enter")
    elif v == "wait":
        if t.isdigit():
            page.wait_for_timeout(int(t))
        elif t:
            page.wait_for_selector(t, timeout=8000)
    elif v == "read":
        reads.append(page.inner_text(t) if t else page.inner_text("body")[:_WEB_MAX_CHARS])


def _browse_do(args):
    url = str(args.get("url", "")).strip()
    ok, why = _safe_url(url)
    if not ok:
        return f"(blocked: {why})"
    actions = _parse_actions(str(args.get("steps", "")))
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return ("(interactive browsing needs Playwright — "
                "pip install playwright && playwright install chromium)")
    reads = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_UA)
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                for act in actions:
                    _do_action(page, act, reads)
                body = page.inner_text("body")
            finally:
                browser.close()
        if reads:
            return "\n".join(reads)[:_WEB_MAX_CHARS] or "(no output)"
        return re.sub(r"\n\s*\n+", "\n", body or "").strip()[:_WEB_MAX_CHARS] or "(no output)"
    except Exception as e:
        return f"(error: {e})"


def build_default_tools(memory=None, allow_web: bool = True,
                        connectors: dict | None = None,
                        browser_pilot=None) -> ToolRegistry:
    reg = ToolRegistry()
    reg.add(Tool("now", "Get the current date and time.",
                 lambda a: time.strftime("%Y-%m-%d %H:%M"), unattended=True))
    reg.add(Tool("calc", "Evaluate a simple arithmetic expression.",
                 _safe_calc, params={"expression": "str"}, unattended=True))
    reg.add(Tool("list_dir", "List files in a directory.",
                 _list_dir, params={"path": "str"}, unattended=True))
    reg.add(Tool("read_file", "Read a text file.",
                 _read_file, params={"path": "str"}, unattended=True))
    reg.add(Tool("write_file", "Write text to a file (needs confirmation).",
                 _write_file, params={"path": "str", "content": "str"}, unattended=False))
    reg.add(Tool("run_shell", "Run a shell command (needs confirmation).",
                 _run_shell, params={"command": "str"}, unattended=False))
    if allow_web:
        reg.add(Tool("web_search", "Search the web and get the top result links.",
                     _web_search, params={"query": "str"}, unattended=True))
        reg.add(Tool("web_fetch", "Fetch a web page (http/https) and read its text.",
                     _web_fetch, params={"url": "str"}, unattended=True))
        reg.add(Tool("browse", "Open a page in a real browser (renders JavaScript) "
                     "and read its text.", _browse, params={"url": "str"}, unattended=True))
        reg.add(Tool("browse_do", "Interact with a page in a real browser — click, "
                     "fill, type, wait, read (one action per line). Needs confirmation.",
                     _browse_do, params={"url": "str", "steps": "str"}, unattended=False))
        if browser_pilot is not None:
            reg.add(Tool("browse_agent", "Autonomously browse toward a goal — observe "
                         "the page, decide, click/fill, repeat. Needs confirmation.",
                         lambda a: browser_pilot.run(str(a.get("url", "")),
                                                     str(a.get("goal", ""))).get("answer", ""),
                         params={"url": "str", "goal": "str"}, unattended=False))
    if connectors is not None:
        from core import connectors as _C
        gr = connectors.get("git_repo") or "."
        cal = connectors.get("calendar_file") or ""
        mbx = connectors.get("mailbox_file") or ""
        gh_repo = connectors.get("github_repo") or ""
        gh_token = connectors.get("github_token") or None
        reg.add(Tool("git_log", "Show recent git commits in a repo.",
                     lambda a: _C.git_log(a.get("path") or gr, int(a.get("n") or 10)),
                     params={"path": "str", "n": "int"}, unattended=True))
        reg.add(Tool("git_status", "Show the git working-tree status of a repo.",
                     lambda a: _C.git_status(a.get("path") or gr),
                     params={"path": "str"}, unattended=True))
        reg.add(Tool("calendar_upcoming", "List upcoming calendar events (.ics file or URL).",
                     lambda a: _C.calendar_upcoming(a.get("path") or cal, int(a.get("days") or 7)),
                     params={"path": "str", "days": "int"}, unattended=True))
        reg.add(Tool("email_recent", "List recent emails from a local mailbox (mbox).",
                     lambda a: _C.email_recent(a.get("path") or mbx, int(a.get("n") or 10)),
                     params={"path": "str", "n": "int"}, unattended=True))
        reg.add(Tool("github_recent", "List recent commits on a GitHub repo (owner/name).",
                     lambda a: _C.github_recent(a.get("repo") or gh_repo, gh_token,
                                                int(a.get("n") or 10)),
                     params={"repo": "str", "n": "int"}, unattended=True))
        if connectors.get("imap_host") and connectors.get("imap_user") \
                and connectors.get("imap_password"):
            reg.add(Tool("email_imap", "List recent email headers over IMAP.",
                         lambda a: _C.imap_recent(connectors["imap_host"],
                                                  connectors["imap_user"],
                                                  connectors["imap_password"],
                                                  int(a.get("n") or 10)),
                         params={"n": "int"}, unattended=True))
    if memory is not None:
        reg.add(Tool("recall", "Search your memory for what you know.",
                     lambda a: _recall(memory, a), params={"query": "str"}, unattended=True))
        reg.add(Tool("remember", "Save a durable fact to memory.",
                     lambda a: _remember(memory, a), params={"fact": "str"}, unattended=True))
    return reg


def _recall(memory, args):
    bundle = memory.retrieve(str(args.get("query", "")), scope=None, budget_tokens=800)
    return " | ".join(c.content for c in bundle.items[:6]) or "(nothing found)"


def _remember(memory, args):
    memory.remember(str(args.get("fact", "")), scope=None)
    return "saved"
