"""Agent — the layer's hands: a governed, model-agnostic tool-use loop.

Give it a task; it reasons in steps, calling tools to actually *do* things (read
files, run a calc, search memory, run a command) until it can answer. This is
what lets agi-layer do tasks and automations itself instead of only routing them
elsewhere.

Two properties make it safe and portable:
  - Governed & fail-closed: every tool call is audited. Tools flagged
    `unattended=False` (write a file, run a shell command) require a `confirm`
    callback that returns True. With no confirm (automation / routines) they are
    denied outright — automations can read, search, and compute, never silently
    write or execute.
  - Model-agnostic: the loop is prompt-based, not vendor tool-calling, so it
    works across every backend (Claude on the subscription, local Qwen, echo
    offline). The model is asked to reply with a single JSON object per step,
    either a tool call or a final answer.
"""
from __future__ import annotations

import json
import re

_SYSTEM = (
    "You are an agent that completes a task by calling tools. On each step reply "
    "with EXACTLY ONE JSON object and nothing else, either:\n"
    '  {"tool": "<name>", "args": {...}}   to call a tool, or\n'
    '  {"final": "<answer>"}               when the task is done.\n'
    "Use only the tools listed below. Keep args minimal and valid JSON. Never add "
    "prose outside the JSON object. Available tools:\n"
)


class Agent:
    def __init__(self, router, tools, audit=None, max_steps: int = 6):
        self.router = router
        self.tools = tools
        self.audit = audit
        self.max_steps = max_steps

    def run(self, task: str, scope: str | None = None, confirm=None) -> dict:
        """Run the loop to completion (or the step limit). Returns
        {"answer": str, "steps": [{"tool","args","result"}, ...]}.

        `confirm(tool_name, args) -> bool` gates non-unattended tools; pass None
        for unattended execution (routines), where such tools are denied."""
        model = self.router.pick(task, None, scope=scope)
        messages = [{"role": "system", "content": self._system()},
                    {"role": "user", "content": f"Task: {task}"}]
        steps: list[dict] = []
        for _ in range(self.max_steps):
            model, reply = self.router.generate(model, messages)
            call = _parse_call(reply)
            if call is None or "final" in call:
                answer = call.get("final") if call else (reply or "").strip()
                return {"answer": answer, "steps": steps}
            name, args = call.get("tool"), call.get("args") or {}
            result = self._invoke(name, args, scope, confirm)
            steps.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user",
                             "content": f"Result of {name}: {result}\nContinue."})
        return {"answer": "(stopped: reached the step limit)", "steps": steps}

    # --- internals ----------------------------------------------------------
    def _invoke(self, name, args, scope, confirm):
        tool = self.tools.get(name)
        if tool is None:
            return f"(no such tool: {name})"
        if not tool.unattended:
            ok = False
            if callable(confirm):
                try:
                    ok = bool(confirm(name, args))
                except Exception:
                    ok = False
            if not ok:
                self._record(name, args, scope, "denied (needs confirmation)")
                return "(denied: this tool needs confirmation)"
        try:
            result = tool.run(args)
        except Exception as e:
            result = f"(error: {e})"
        self._record(name, args, scope, "ran")
        return result

    def _record(self, name, args, scope, status):
        if self.audit is None:
            return
        try:
            self.audit.record("tool_call", None,
                              {"tool": name, "args": args, "scope": scope}, status)
        except Exception:
            pass

    def _system(self) -> str:
        lines = []
        for s in self.tools.specs():
            gate = "" if s["unattended"] else "  [needs confirmation]"
            lines.append(f"  - {s['name']}({', '.join(s['args'])}): "
                         f"{s['description']}{gate}")
        return _SYSTEM + "\n".join(lines)


def _parse_call(text):
    """Accept the first JSON object that is a tool call or a final answer.
    Tolerant of models that wrap the JSON in prose or code fences."""
    if not text:
        return None
    for candidate in (text, _first_object(text)):
        if not candidate:
            continue
        try:
            v = json.loads(candidate)
        except Exception:
            continue
        if isinstance(v, dict) and ("tool" in v or "final" in v):
            return v
    return None


def _first_object(text):
    m = re.search(r"\{.*\}", text, re.S)
    return m.group(0) if m else None
