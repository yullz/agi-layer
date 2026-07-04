"""Local model adapter — Ollama (and Ollama-compatible runtimes).

Used for privacy-sensitive tasks, cheap high-volume calls, and as an always-on
fallback. Talks the Ollama HTTP API with the standard library only (no extra
deps). `available()` does a fast reachability probe so the router can skip a
runtime that isn't running.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class LocalModel:
    def __init__(self, model_name: str, endpoint: str = "http://localhost:11434", **opts):
        self.model_name = model_name
        self.endpoint = endpoint.rstrip("/")
        self.opts = opts

    def available(self, timeout: float = 0.5) -> bool:
        """Quick reachability check so the router can fall back when the local
        runtime isn't up."""
        try:
            with urllib.request.urlopen(f"{self.endpoint}/api/tags", timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False

    def generate(self, prompt, tools=None) -> str:
        messages = prompt if isinstance(prompt, list) else [
            {"role": "user", "content": str(prompt)}]
        payload = {"model": self.model_name, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            f"{self.endpoint}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Local model unreachable at {self.endpoint} ({e}). Is Ollama running?"
            ) from e
        return (body.get("message") or {}).get("content", "")
