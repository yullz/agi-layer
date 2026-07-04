"""LLM-driven fact extraction + contradiction detection.

Turns reconcile-on-write from a heuristic into real memory hygiene: an LLM
(local, for privacy) extracts durable facts from a turn and judges whether a new
fact restates, contradicts, or is unrelated to an existing one — which is what
lets the native store *supersede* stale facts instead of only deduping.

Degrades cleanly: when the model is unavailable, callers fall back to the
heuristic extractor and dedup-only reconcile.
"""
from __future__ import annotations

import json
import re

_EXTRACT_SYS = (
    "Extract durable facts about the user worth remembering long-term from the "
    "exchange. Output a JSON array of short factual strings (e.g. "
    "[\"lives in Berlin\", \"prefers Python\"]). Output [] if nothing is durable. "
    "Be stingy — precision over recall; a wrong fact is worse than a missing one."
)
_JUDGE_SYS = (
    "Compare two statements about the user. Reply with exactly ONE word: "
    "SAME (the new restates the old), CONTRADICTS (the new updates/replaces the "
    "old), or UNRELATED."
)
_RELATION_SYS = (
    "Extract relationships as JSON triples [subject, predicate, object] about "
    "the user's world (people, projects, tools, places). Predicate is a short "
    "snake_case verb (works_on, uses, lives_in, prefers, knows). Output a JSON "
    "array of 3-element arrays; [] if none. Keep subject/object short."
)


class LLMExtractor:
    def __init__(self, model):
        self.model = model

    def available(self) -> bool:
        probe = getattr(self.model, "available", None)
        if callable(probe):
            try:
                return bool(probe())
            except Exception:
                return False
        return self.model is not None

    def extract(self, user_input: str, assistant_reply: str | None = None) -> list[str]:
        convo = f"User: {user_input}"
        if assistant_reply:
            convo += f"\nAssistant: {assistant_reply}"
        reply = self.model.generate(
            [{"role": "system", "content": _EXTRACT_SYS},
             {"role": "user", "content": convo}])
        return _parse_json_list(reply)

    def judge(self, new_fact: str, old_fact: str) -> str:
        """Return 'same' | 'contradicts' | 'unrelated'."""
        reply = self.model.generate(
            [{"role": "system", "content": _JUDGE_SYS},
             {"role": "user", "content": f"OLD: {old_fact}\nNEW: {new_fact}"}])
        r = (reply or "").strip().lower()
        if "contradict" in r:
            return "contradicts"
        if "same" in r:
            return "same"
        return "unrelated"

    def extract_relations(self, text: str) -> list[tuple]:
        """Return typed (subject, predicate, object) triples for the graph."""
        reply = self.model.generate(
            [{"role": "system", "content": _RELATION_SYS},
             {"role": "user", "content": text or ""}])
        return _parse_triples(reply)


def _parse_json_list(text: str) -> list[str]:
    if not text:
        return []
    for candidate in (text, _first_bracket(text)):
        if not candidate:
            continue
        try:
            v = json.loads(candidate)
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
        except Exception:
            continue
    return []


def _first_bracket(text: str):
    m = re.search(r"\[.*\]", text, re.S)
    return m.group(0) if m else None


def _first_json_array(text: str):
    if not text:
        return []
    for candidate in (text, _first_bracket(text)):
        if not candidate:
            continue
        try:
            v = json.loads(candidate)
            if isinstance(v, list):
                return v
        except Exception:
            continue
    return []


def _parse_triples(text: str) -> list[tuple]:
    out = []
    for row in _first_json_array(text):
        if isinstance(row, (list, tuple)) and len(row) >= 3:
            s, p, o = str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip()
            if s and o:
                out.append((s, p or "related_to", o))
    return out
