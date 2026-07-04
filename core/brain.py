"""Brain preference — local-first vs. auto-route.

By default the router sends everyday chat to the best available model (Claude on
your plan, if configured) and keeps the on-box model for sensitive scopes. Some
people would rather keep *everything* on the local model — private and free, even
if a cloud brain is set up. This module flips that preference by writing the two
general-purpose routing intents to the local model (sensitive scopes are already
forced local, and the fallback is unchanged), and persists the choice.

It never removes the cloud model — turning the preference back to "auto" restores
normal routing instantly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_INTENTS = ("general", "hard_reasoning")


def local_model_name(registry) -> str | None:
    """The registry name of an on-box model to route to — the configured private
    default if it's local, else any local backend. None if there's no local model
    (e.g. Ollama isn't set up), in which case we leave routing alone."""
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


def apply_preference(policy, registry, prefer_local: bool) -> bool:
    """Set (or clear) the local-first routing rules on the live policy. Returns
    the effective preference — False if 'local' was asked for but no local model
    exists to route to."""
    rules = dict(getattr(policy, "routing_rules", None) or {})
    if prefer_local:
        name = local_model_name(registry)
        if not name:
            return False
        for intent in _INTENTS:
            rules[intent] = name
    else:
        for intent in _INTENTS:
            rules.pop(intent, None)
    policy.routing_rules = rules
    return bool(prefer_local)


def is_local_preferred(policy, registry) -> bool:
    """True when the general intent is currently pinned to a local model."""
    rules = getattr(policy, "routing_rules", None) or {}
    name = rules.get("general")
    if not name:
        return False
    m = registry.get(name)
    return m is not None and getattr(m, "is_local", False)


# --- persistence (a tiny marker in the data dir) ----------------------------
def _file(data_dir) -> Path:
    return Path(data_dir) / "brain.json"


def load_pref(data_dir) -> bool | None:
    """Saved preference, or None if the user hasn't chosen yet."""
    try:
        with open(_file(data_dir), encoding="utf-8") as f:
            return bool(json.load(f).get("prefer_local"))
    except Exception:
        return None


def save_pref(data_dir, prefer_local: bool) -> None:
    p = _file(data_dir)
    try:
        os.makedirs(p.parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"prefer_local": bool(prefer_local)}, f, indent=2)
    except Exception:
        pass
