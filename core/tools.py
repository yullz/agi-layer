"""Tools the agent can call to actually *do* things — the hands of the layer.

Each Tool declares whether it's `unattended` (safe to run without asking — the
clock, arithmetic, reading memory/files) or not (writing files, running commands
— these need confirmation and are denied outright in automation contexts). The
agent loop enforces that and audits every call.
"""
from __future__ import annotations

import ast
import operator
import os
import subprocess
import time


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


def build_default_tools(memory=None) -> ToolRegistry:
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
