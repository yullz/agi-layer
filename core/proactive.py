"""Proactive / active-learning layer — the assistant reaches out.

Two moves that make it feel alive instead of a passive database:
  * active learning — detect gaps in what it knows about the user, and ask.
  * proactive recall — surface what's important/recent unprompted (a briefing).

Everything reads through MemoryStore.retrieve, so it inherits scope + privacy for
free. Heuristic slot detection now; an LLM can sharpen it later.
"""
from __future__ import annotations

from memory.schema import Source

# Profile slots the layer likes to know about its user. `kw` = phrases that,
# if already in memory, mean the slot is filled.
_SLOTS = [
    {"key": "name", "q": "What should I call you?",
     "kw": ("name is", "call you", "call me")},
    {"key": "timezone", "q": "What timezone are you in?",
     "kw": ("timezone", "time zone", "utc", "gmt", "pst", "cet", "est")},
    {"key": "focus", "q": "What are you focused on right now?",
     "kw": ("working on", "focused on", "building", "shipping")},
    {"key": "working hours", "q": "When do you usually work?",
     "kw": ("work hours", "working hours", "mornings", "evenings", "9 to 5", "at night")},
    {"key": "role", "q": "What do you do — your role or main work?",
     "kw": ("i work as", "my role", "i'm a ", "i am a ", "founder", "engineer",
            "developer", "designer", "manager")},
]

# How to phrase the user's answer as a stored fact.
_PHRASE = {
    "name": "My name is", "timezone": "My timezone is",
    "focus": "I'm currently focused on", "working hours": "I usually work",
    "role": "I work as",
}


class Proactive:
    def __init__(self, memory):
        self.memory = memory

    def gaps(self, scope=None) -> list[dict]:
        """Profile slots the layer doesn't yet know — candidates to ask about."""
        out = []
        for slot in _SLOTS:
            bundle = self.memory.retrieve(slot["key"], scope=scope, budget_tokens=500)
            blob = " ".join(c.content.lower() for c in bundle.items)
            if not any(k in blob for k in slot["kw"]):
                out.append(slot)
        return out

    def next_question(self, scope=None):
        g = self.gaps(scope)
        return g[0] if g else None

    def fact_from_answer(self, slot, answer: str) -> str:
        prefix = _PHRASE.get(slot["key"], "My " + slot["key"] + " is")
        return f"{prefix} {answer.strip()}."

    def briefing(self, scope=None, limit: int = 5) -> list[str]:
        """Proactive recall: the most important/recent durable facts."""
        bundle = self.memory.retrieve("", scope=scope, budget_tokens=1200)
        return [c.content for c in bundle.items
                if c.source in (Source.VECTOR, Source.GRAPH)][:limit]
