"""Skill registry + Voyager-style self-authoring.

Holds the tools the layer can call, and can *write new ones* when it hits a
capability gap: an LLM drafts a Python `skill(payload)` function, it's statically
screened + run in a restricted namespace against a test input, and registered on
success. Governed: authoring is gated by guardrails (fail-closed by default —
'skill_author' must be explicitly allowed) and logged to the audit trail.

SECURITY NOTE: the restricted-namespace exec is a basic guard, NOT a hardened
sandbox. Keep authoring disabled (the default) unless you trust the model; for
real isolation, run skills in a subprocess/container.
"""
from __future__ import annotations

import builtins
import json
import os
import re
import threading

_FORBIDDEN = ("import os", "import sys", "import subprocess", "import socket",
              "import shutil", "__import__", "open(", "eval(", "exec(",
              "compile(", "globals(", "getattr(", "setattr(", "input(")

_SAFE_BUILTINS = {k: getattr(builtins, k) for k in (
    "len", "range", "min", "max", "sum", "abs", "round", "sorted", "str", "int",
    "float", "bool", "list", "dict", "set", "tuple", "enumerate", "zip", "map",
    "filter", "any", "all", "reversed") if hasattr(builtins, k)}

_AUTHOR_SYS = (
    "Write a single Python function `def skill(payload: dict):` that solves the "
    "described capability gap. Use only builtins and pure Python — NO imports, "
    "file I/O, or network. Return the result. Output ONLY the function code."
)


class Skills:
    def __init__(self, model=None, registry_dir=None, guardrails=None, audit=None):
        self.model = model
        self.dir = str(registry_dir) if registry_dir else None
        self.guardrails = guardrails
        self.audit = audit
        self._skills: dict = {}   # name -> {"code","description","func"}
        if self.dir:
            os.makedirs(self.dir, exist_ok=True)
            self._load()

    # --- registry -----------------------------------------------------------
    def _load(self) -> None:
        try:
            with open(os.path.join(self.dir, "manifest.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        for name, desc in meta.items():
            try:
                with open(os.path.join(self.dir, f"{name}.py"), encoding="utf-8") as f:
                    code = f.read()
                func = _build(code)
                if func:
                    self._skills[name] = {"code": code, "description": desc, "func": func}
            except Exception:
                continue

    def available(self, scope: str | None = None) -> list:
        return [{"name": n, "description": s["description"]} for n, s in self._skills.items()]

    def get(self, name: str):
        s = self._skills.get(name)
        return s["func"] if s else None

    def _register(self, name: str, code: str, description: str, func) -> None:
        self._skills[name] = {"code": code, "description": description, "func": func}
        if not self.dir:
            return
        with open(os.path.join(self.dir, f"{name}.py"), "w", encoding="utf-8") as f:
            f.write(code)
        with open(os.path.join(self.dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({n: s["description"] for n, s in self._skills.items()}, f)

    # --- authoring ----------------------------------------------------------
    def author(self, gap_description: str, *, test_input=None) -> dict:
        """Draft, screen, sandbox-test, and register a new skill. Gated by
        guardrails (fail-closed) and audited."""
        action = "skill_author"
        if self.guardrails is not None and not self.guardrails.allow(action, {"gap": gap_description}):
            if self.audit is not None:
                self.audit.record(action, None, None, f"DENIED: {gap_description}")
            return {"status": "denied-by-governance"}
        if self.model is None:
            return {"status": "no-model"}
        code = _extract_code(self.model.generate(
            [{"role": "system", "content": _AUTHOR_SYS},
             {"role": "user", "content": gap_description}]))
        ok, err = _screen(code)
        if not ok:
            return {"status": "rejected", "error": err}
        func = _build(code)
        if func is None:
            return {"status": "build-failed"}
        passed, err = _sandbox_test(func, test_input if test_input is not None else {})
        if not passed:
            return {"status": "sandbox-failed", "error": err}
        name = _slug(gap_description)
        self._register(name, code, gap_description, func)
        if self.audit is not None:
            self.audit.record(action, None, {"skill": name}, f"authored: {gap_description}")
        return {"status": "registered", "name": name}


# --- module helpers ---------------------------------------------------------
def _extract_code(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def _screen(code: str):
    if "def skill" not in code:
        return False, "no `def skill` defined"
    low = code.lower()
    for bad in _FORBIDDEN:
        if bad in low:
            return False, f"forbidden construct: {bad}"
    try:
        compile(code, "<skill>", "exec")
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    return True, ""


def _build(code: str):
    try:
        ns: dict = {}
        exec(compile(code, "<skill>", "exec"), {"__builtins__": _SAFE_BUILTINS}, ns)
        fn = ns.get("skill")
        return fn if callable(fn) else None
    except Exception:
        return None


def _sandbox_test(func, payload):
    result = {"ok": False, "err": ""}

    def _run():
        try:
            func(payload)
            result["ok"] = True
        except Exception as e:
            result["err"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=2.0)
    if t.is_alive():
        return False, "timeout"
    return result["ok"], result["err"]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "skill").lower()).strip("_")
    return s[:40] or "skill"
