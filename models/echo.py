"""Echo model — a zero-dependency, offline backend.

Not an assistant: it echoes the user's last message and states that no real
model is configured. Its job is to make the whole turn loop runnable out of the
box (no API key, no Ollama) so you can exercise memory + routing before wiring a
real model. The router falls back to this when nothing else is reachable. Swap
it out the moment a frontier key or a local runtime is up.
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
        user = _last_user(prompt)
        return (
            f"[echo] No real model is configured yet, so I can't reason — but I "
            f"received: {user!r}. Set a frontier API key or start a local Ollama "
            f"model to enable real replies."
        )


def _last_user(prompt) -> str:
    """Pull the last user message out of whatever prompt shape we got — a
    messages list of {role, content}, or a plain string."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        for msg in reversed(prompt):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return str(msg.get("content", ""))
        if prompt:
            last = prompt[-1]
            return str(last.get("content", last) if isinstance(last, dict) else last)
    return str(prompt)
