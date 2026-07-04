"""Brain selection — which model answers, and how hard it thinks.

By default Myro routes each turn to the best available model (Auto). You can
instead pin a specific model so every prompt uses it until you change it — your
local model (private + free), a specific Claude model, or the offline echo — via
`apply_choice`. Sensitive scopes always stay on the local model regardless.

`effort` is a light steer for how thorough the answer should be; it's applied to
the Claude backend (which honours it in how it reasons). The chosen model +
effort persist in data/brain.json so they survive restarts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# The two general-purpose routing intents we override to pin a model. (Sensitive
# scope is handled separately and always local.)
_INTENTS = ("general", "hard_reasoning")

EFFORTS = ("quick", "balanced", "thorough")
DEFAULT_EFFORT = "balanced"

# Friendly labels for the picker; unknown model names fall back to themselves.
_LABELS = {
    "qwen-local": "Local · private & free",
    "claude-opus": "Claude Opus · deepest",
    "claude-sonnet": "Claude Sonnet · fast",
    "echo": "Offline (echo)",
}


def label_for(name: str) -> str:
    return _LABELS.get(name, name)


def local_model_name(registry) -> str | None:
    """Registry name of an on-box model (the private default if local, else any
    local backend). None when there's no local model configured."""
    priv = registry.default_name("private")
    if priv:
        m = registry.get(priv)
        if m is not None and getattr(m, "is_local", False):
            return priv
    for n in registry.names():
        m = registry.get(n)
        if m is not None and getattr(m, "is_local", False) and n != "echo":
            return n
    return None


def options(registry) -> list[dict]:
    """The picker's choices: Auto first, then every registered model."""
    out = [{"value": "auto", "label": "Auto · best for each task"}]
    for n in registry.names():
        out.append({"value": n, "label": label_for(n)})
    return out


def apply_choice(policy, registry, choice: str) -> str:
    """Pin the model for everyday turns (or clear the pin for Auto). `choice` is
    'auto', 'local', or a registry model name. Returns the effective choice
    ('auto' when the requested model doesn't exist)."""
    choice = (choice or "auto").strip()
    rules = dict(getattr(policy, "routing_rules", None) or {})
    if choice in ("auto", ""):
        for intent in _INTENTS:
            rules.pop(intent, None)
        policy.routing_rules = rules
        return "auto"
    name = local_model_name(registry) if choice == "local" else choice
    if not name or registry.get(name) is None:
        for intent in _INTENTS:
            rules.pop(intent, None)
        policy.routing_rules = rules
        return "auto"
    for intent in _INTENTS:
        rules[intent] = name
    policy.routing_rules = rules
    return name


def current_choice(policy, registry) -> str:
    """The pinned model name, or 'auto' when nothing is pinned."""
    name = (getattr(policy, "routing_rules", None) or {}).get("general")
    if name and registry.get(name) is not None:
        return name
    return "auto"


def set_effort(registry, effort: str) -> str:
    """Record the effort level on the cloud (Claude) adapters so their next call
    honours it. Local/echo ignore it. Returns the normalised effort."""
    effort = (effort or DEFAULT_EFFORT).strip().lower()
    if effort not in EFFORTS:
        effort = DEFAULT_EFFORT
    for n in registry.names():
        m = registry.get(n)
        if m is not None and not getattr(m, "is_local", False):
            try:
                m.effort = effort
            except Exception:
                pass
    return effort


def current_effort(registry) -> str:
    for n in registry.names():
        m = registry.get(n)
        if m is not None and not getattr(m, "is_local", False):
            e = getattr(m, "effort", None)
            if e in EFFORTS:
                return e
    return DEFAULT_EFFORT


# --- persistence (a small marker in the data dir) ---------------------------
def _file(data_dir) -> Path:
    return Path(data_dir) / "brain.json"


def load_state(data_dir) -> dict:
    """{'model': <choice or None>, 'effort': <level or None>}. Empty when unset.
    Understands the older {'prefer_local': true} marker for a smooth upgrade."""
    try:
        with open(_file(data_dir), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    model = data.get("model")
    if model is None and data.get("prefer_local"):
        model = "local"
    return {"model": model, "effort": data.get("effort")}


def save_state(data_dir, model: str, effort: str) -> None:
    p = _file(data_dir)
    try:
        os.makedirs(p.parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"model": model, "effort": effort}, f, indent=2)
    except Exception:
        pass
