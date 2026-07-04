"""Frontier model adapter — Claude / GPT / Gemini via LiteLLM.

Routing every provider through one LiteLLM call keeps the rest of the system
provider-agnostic: swapping Claude for GPT is a config change. A model is only
"available" when its provider's API key is present, so the router won't route to
a backend it can't authenticate against.
"""
from __future__ import annotations

import os

# Map our short config names to LiteLLM model ids. Extend as you add models.
_LITELLM_IDS = {
    "claude-opus": "anthropic/claude-opus-4-20250514",
    "claude-sonnet": "anthropic/claude-sonnet-4-20250514",
}

# Which env var must be present for a provider to be usable.
_PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
}


class FrontierModel:
    def __init__(self, model_name: str, provider: str | None = None, **opts):
        self.model_name = model_name
        self.provider = provider
        self.opts = opts
        self.litellm_id = _LITELLM_IDS.get(model_name) or (
            f"{provider}/{model_name}" if provider else model_name)

    def available(self) -> bool:
        """Usable only if the provider's API key is present in the environment."""
        env = _PROVIDER_KEY_ENV.get((self.provider or "").lower())
        return bool(env and os.environ.get(env))

    def generate(self, prompt, tools=None) -> str:
        try:
            import litellm
        except Exception as e:  # pragma: no cover - depends on install
            raise RuntimeError(
                "litellm is not installed — `pip install litellm` to use frontier models."
            ) from e
        messages = prompt if isinstance(prompt, list) else [
            {"role": "user", "content": str(prompt)}]
        kwargs = {"model": self.litellm_id, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = litellm.completion(**kwargs)
        # Single completion; the full tool-call loop (execute tool -> feed
        # result -> repeat) is a Phase-3 addition.
        return resp["choices"][0]["message"]["content"] or ""
