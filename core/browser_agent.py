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
                # Richer perception: attach a screenshot for vision-capable models
                # (the model advertises supports_vision). Text-only otherwise.
                vision = bool(getattr(model, "supports_vision", False))
                shot = None
                if vision and hasattr(session, "screenshot"):
                    try:
                        shot = session.screenshot()
                    except Exception:
                        shot = None
                messages = _build_messages(goal, obs, steps, shot, vision)
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


# --- perception (pure, so the Playwright adapter stays thin + testable) ------
_AX_SKIP = {"generic", "none", "presentation", "InlineTextBox", "LineBreak", "text"}


def _flatten_ax(node, limit: int = 40) -> list:
    """Flatten a Playwright accessibility snapshot to compact `role "name"`
    lines — the semantic skeleton a model reasons over far better than raw DOM."""
    out: list[str] = []

    def walk(n):
        if not isinstance(n, dict) or len(out) >= limit:
            return
        role, name = n.get("role"), (n.get("name") or "").strip()
        if role and role not in _AX_SKIP:
            out.append(f'{role} "{name}"' if name else role)
        for c in (n.get("children") or []):
            walk(c)

    walk(node or {})
    return out[:limit]


def _format_observation(url: str, text: str, elements, ax_lines) -> str:
    parts = [f"URL: {url}", "TEXT:", (text or "")[:2500]]
    if ax_lines:
        parts += ["ACCESSIBILITY (role \"name\"):", "\n".join(f"- {a}" for a in ax_lines)]
    if elements:
        parts += ["ELEMENTS:", "\n".join(f"- {e}" for e in elements)]
    return "\n".join(parts)


def _build_messages(goal: str, obs: str, history, screenshot_b64=None,
                    supports_vision: bool = False) -> list:
    """Assemble the per-step messages. For a vision model with a screenshot, the
    user turn is multimodal (text + image); otherwise it's plain text — so a
    non-vision backend never receives an image it can't handle."""
    if supports_vision and screenshot_b64:
        # OpenAI/LiteLLM-compatible image part (a data: URI). A provider adapter
        # can translate this to the Anthropic-native shape if needed.
        user_content = [
            {"type": "text", "text": f"GOAL: {goal}\n\n{obs}"},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}},
        ]
    else:
        user_content = f"GOAL: {goal}\n\n{obs}"
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content}]
    for s in (history or [])[-3:]:
        messages.append({"role": "assistant", "content": json.dumps(s["action"])})
        messages.append({"role": "user", "content": f"(did that: {s['result']})"})
    return messages


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
        try:
            ax = self.page.accessibility.snapshot()
        except Exception:
            ax = None
        return _format_observation(self.page.url, text, els, _flatten_ax(ax))

    def screenshot(self):
        """Base64 PNG of the current viewport, for vision models. None on error."""
        try:
            import base64
            png = self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(png).decode("ascii")
        except Exception:
            return None

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
