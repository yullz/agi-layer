"""Lightweight entity extraction for graph population.

A heuristic first cut — capitalised, alphanumeric tokens of length >= 3, minus
common sentence-initial words. Good enough to start filling the knowledge graph
from raw turns; replace with an NER pass or an LLM extractor for precision.
"""
from __future__ import annotations

import re

_STOP = {
    "The", "This", "That", "These", "Those", "And", "But", "For", "With",
    "You", "Your", "Yours", "Our", "Ours", "They", "Them", "His", "Her",
    "She", "Him", "Was", "Were", "Are", "Has", "Have", "Had", "Not", "Can",
    "Could", "Would", "Should", "When", "What", "Why", "How", "Where", "Who",
    "Its", "Remember", "Got", "Note", "Hello", "Hi", "Set", "Use", "Using",
    "Please", "Thanks", "Okay",
}


def extract_entities(text: str, limit: int = 12) -> list[str]:
    seen: dict[str, None] = {}
    for raw in (text or "").split():
        tok = raw.strip(".,:;!?\"'()[]{}")
        if len(tok) < 3 or not tok[0].isupper() or not tok.isalnum():
            continue
        if tok in _STOP:
            continue
        seen.setdefault(tok, None)
        if len(seen) >= limit:
            break
    return list(seen)


# First-person cues that mark a durable statement about the user. Deliberately
# excludes bare " me " (matches questions like "what do you know about me").
_CUE = (" i ", " i'm ", " i've ", " my ", " mine ", " we ", " our ")
_QUESTION_STARTS = ("what", "why", "how", "when", "where", "who", "which", "do ",
                    "does", "did", "can ", "could", "would", "is ", "are ", "will")


def extract_facts(text: str, max_facts: int = 5) -> list[str]:
    """Heuristic candidate durable facts: declarative sentences that talk about
    the user (a first-person cue), skipping questions. Replace with an LLM
    extractor for precision — the reconcile step downstream dedups the output."""
    facts = []
    for chunk in re.split(r"[.\n]+", text or ""):
        # Split on . / newline only, so a trailing '?' is preserved to detect
        # (and skip) questions.
        for sent in re.split(r"(?<=[?!])\s+", chunk):
            s = sent.strip()
            if len(s) < 8 or s.endswith("?"):
                continue
            low_s = s.lower()
            if low_s.startswith(_QUESTION_STARTS):
                continue
            low = f" {low_s} "
            if low_s.startswith(("i ", "my ", "i'm", "i've")) or any(c in low for c in _CUE):
                facts.append(s)
            if len(facts) >= max_facts:
                return facts
    return facts
