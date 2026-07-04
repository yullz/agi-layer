"""Lightweight entity extraction for graph population.

A heuristic first cut — capitalised, alphanumeric tokens of length >= 3, minus
common sentence-initial words. Good enough to start filling the knowledge graph
from raw turns; replace with an NER pass or an LLM extractor for precision.
"""
from __future__ import annotations

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
