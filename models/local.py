"""Local model adapter — Ollama / vLLM / llama.cpp."""
from __future__ import annotations


class LocalModel:
    def __init__(self, model_name: str, endpoint: str = "http://localhost:11434", **opts):
        self.model_name = model_name
        self.endpoint = endpoint
        self.opts = opts

    def generate(self, prompt, tools=None) -> str:
        """Call the local runtime. Used for privacy-sensitive tasks (scope
        flags them), cheap high-volume calls, and as an always-on fallback
        when frontier APIs are unreachable.
        """
        raise NotImplementedError("Wire Ollama/vLLM; see ARCHITECTURE.md (Model layer)")
