"""Echo model — a zero-dependency, offline backend.

Not an assistant: it's a friendly placeholder so the whole turn loop runs out of
the box (no API key, no Ollama) while still saving everything to memory. The
router falls back to this when nothing else is reachable; swap it out the moment
a frontier key or a local runtime is up.
"""
from __future__ import annotations


class EchoModel:
    is_local = True  # on-box, safe as a sensitive-scope last resort

    def __init__(self, name: str = "echo", **opts):
        self.model_name = name or "echo"
        self.opts = opts

    def available(self) -> bool:
        return True

    def generate(self, prompt, tools=None) -> str:
        return (
            "I'm in offline mode right now (no model configured), so I can't reason "
            "about that properly yet — but I've kept it in memory. Start a local "
            "Ollama model or set an API key to switch me on."
        )
