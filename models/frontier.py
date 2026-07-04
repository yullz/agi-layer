"""Frontier model adapter — Claude / GPT / Gemini via LiteLLM."""
from __future__ import annotations


class FrontierModel:
    def __init__(self, model_name: str, **opts):
        self.model_name = model_name
        self.opts = opts

    def generate(self, prompt, tools=None) -> str:
        """Call the frontier model (litellm.completion) and run the tool loop.
        Routing every provider through one LiteLLM call keeps the rest of the
        system provider-agnostic — swapping Claude for GPT is a config change.
        """
        raise NotImplementedError("Wire LiteLLM; see ARCHITECTURE.md (Model layer)")
