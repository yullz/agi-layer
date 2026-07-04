"""BrowserPilot — a perceive-act browsing loop.

Where `browse_do` runs a fixed script, this *decides as it goes*: it observes the
page (visible text + interactive elements), asks the model for the single next
action, performs it, observes again, and repeats until the goal is met or a step
limit is hit. That's what lets it handle flows it can't pre-plan (multi-step
forms, "click Next until you find X").

Two design choices keep it testable and safe:
  - The browser I/O is behind a small session interface (`observe()` / `act()` /
    `close()`), so the loop logic runs offline against a fake session — the
    Playwright adapter is thin. The SSRF guard runs before any browser launch.
  - It's driven by the router like the main agent, and it's exposed as a GATED
    tool (`browse_agent`, unattended=False): the user approves the *session*
    once, then the pilot acts autonomously toward the goal within it. It's denied
    in unattended automations, fail-closed.
"""
from __future__ import annotations

import json
import re

from core.tools import _UA, _WEB_MAX_CHARS, _safe_url

_SYSTEM = (
    "You are driving a web browser to accomplish a goal. Each turn you get an "
    "observation (the page URL, visible text, and interactive ELEMENTS). Reply "
    "with EXACTLY ONE JSON object and nothing else, either an action:\n"
    '  {"action": "click|fill|type|select|press|wait|read", "target": "<selector '
    'or text=…>", "value": "<for fill/select>"}\n'
    "or, when the goal is met, the final answer:\n"
    '  {"done": "<answer>"}\n'
    "Targets are CSS or text= selectors from the ELEMENTS list. Be efficient."
)


class BrowserPilot:
    def __init__(self, router, max_steps: int = 8):
        self.router = router
        self.max_steps = max_steps

    def run(self, url: str, goal: str, session=None, scope: str | None = None) -> dict:
        own = session is None
        if own:
            ok, why = _safe_url(url)
            if not ok:
                return {"answer": f"(blocked: {why})", "steps": []}
            try:
                session = _PlaywrightSession(url)
            except ImportError:
                return {"answer": "(browse_agent needs Playwright — pip install "
                                  "playwright && playwright install chromium)", "steps": []}
            except Exception as e:
                return {"answer": f"(error: {e})", "steps": []}
        try:
            model = self.router.pick(goal, None, scope=scope)
            steps: list[dict] = []
            for _ in range(self.max_steps):
                obs = session.observe()
                messages = [{"role": "system", "content": _SYSTEM},
                            {"role": "user", "content": f"GOAL: {goal}\n\n{obs}"}]
                for s in steps[-3:]:
                    messages.append({"role": "assistant", "content": json.dumps(s["action"])})
                    messages.append({"role": "user", "content": f"(did that: {s['result']})"})
                model, reply = self.router.generate(model, messages)
                action = _parse_action(reply)
                if action is None or "done" in action:
                    answer = action.get("done") if action else (reply or "").strip()
                    return {"answer": answer, "steps": steps}
                result = session.act(action)
                steps.append({"action": action, "result": result})
            return {"answer": "(stopped: reached the step limit)", "steps": steps}
        finally:
            if own:
                try:
                    session.close()
                except Exception:
                    pass


def _parse_action(text):
    if not text:
        return None
    for candidate in (text, _first_object(text)):
        if not candidate:
            continue
        try:
            v = json.loads(candidate)
        except Exception:
            continue
        if isinstance(v, dict) and ("action" in v or "done" in v):
            return v
    return None


def _first_object(text):
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0) if m else None


class _PlaywrightSession:
    """Thin Playwright adapter: observe() snapshots the page, act() performs one
    DSL action. Kept minimal on purpose — the tested logic is in the loop."""

    def __init__(self, url: str):
        from playwright.sync_api import sync_playwright  # may raise ImportError
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        self.page = self.browser.new_page(user_agent=_UA)
        self.page.goto(url, timeout=20000, wait_until="domcontentloaded")

    def observe(self) -> str:
        text = self.page.inner_text("body")[:2500]
        try:
            els = self.page.eval_on_selector_all(
                "a,button,input,textarea,select",
                "els => els.slice(0,40).map(e => (e.tagName+' '+"
                "((e.getAttribute&&e.getAttribute('type'))||'')+' '+"
                "((e.innerText||e.value||e.placeholder||e.name||'').slice(0,60))).trim())")
        except Exception:
            els = []
        return (f"URL: {self.page.url}\nTEXT:\n{text}\n"
                f"ELEMENTS:\n" + "\n".join(f"- {e}" for e in els))

    def act(self, action: dict) -> str:
        from core.tools import _do_action  # reuse the browse_do action executor
        verb = action.get("action", "")
        reads: list[str] = []
        try:
            _do_action(self.page, {"verb": verb, "target": action.get("target", ""),
                                   "value": action.get("value", "")}, reads)
        except Exception as e:
            return f"(error: {e})"
        if reads:
            return reads[0][:_WEB_MAX_CHARS]
        return "ok"

    def close(self) -> None:
        try:
            self.browser.close()
        finally:
            self._pw.stop()
