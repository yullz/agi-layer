"""Seed memory — bootstrap the layer with what we already know about the user.

Populates the semantic store (durable facts) and the knowledge graph (typed
relations) so the layer starts already knowing you, then accrues the rest as you
use it. Facts here come from our design conversations — edit freely, they're
yours. Run via the CLI ':seed' or seed_memory(memory).

Note: these are seeded at global scope (None). Re-seed per project scope, or
query at the global scope, to surface them.
"""
from __future__ import annotations

from memory.schema import ItemKind, MemoryItem

# Durable facts about the user (edit/extend as you like).
SEED_FACTS = [
    "You are building agi-layer: a local-first personal intelligence layer.",
    "You value privacy and local-first design; sensitive data should stay on your machine.",
    "You run several parallel projects and use scopes to keep them separate.",
    "You use OpenClaw and built model routing in it.",
    "You use Claude Skills and have a Claude Max subscription.",
    "Your machine is Windows with an RTX 4070 Super (16GB) GPU.",
    "You prefer Qwen local models for private work and Claude for hard reasoning.",
]

# Typed relations: (subject, predicate, object).
SEED_RELATIONS = [
    ("You", "works_on", "The Longevity Code"),
    ("You", "works_on", "WhaleTrack"),
    ("You", "works_on", "Ocado"),
    ("You", "works_on", "Felt & Paper"),
    ("You", "builds", "agi-layer"),
    ("You", "uses", "OpenClaw"),
    ("You", "uses", "Claude"),
    ("You", "uses", "Ollama"),
    ("WhaleTrack", "uses", "Docker"),
    ("agi-layer", "runs_on", "Windows"),
]


def seed_memory(memory, scope: str | None = None) -> dict:
    """Load the seed facts + relations into `memory` (a MemoryStore). Returns a
    small report. Idempotent-ish: the semantic store dedups on reconcile."""
    facts = 0
    semantic = getattr(memory, "semantic", None)
    if semantic is not None and hasattr(semantic, "upsert"):
        for content in SEED_FACTS:
            try:
                semantic.upsert(MemoryItem(content=content, kind=ItemKind.FACT,
                                           scope=scope, importance=0.8))
                facts += 1
            except Exception:
                pass

    rels = 0
    graph = getattr(memory, "graph", None)
    if graph is not None and hasattr(graph, "get_or_create_entity"):
        for s, p, o in SEED_RELATIONS:
            try:
                sid = graph.get_or_create_entity(s, scope=scope)
                oid = graph.get_or_create_entity(o, scope=scope)
                graph.relate(sid, oid, p, scope=scope)
                rels += 1
            except Exception:
                pass
    return {"facts": facts, "relations": rels}
