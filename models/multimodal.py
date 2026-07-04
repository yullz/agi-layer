"""Helpers for multimodal message content.

An attached image rides in a message as OpenAI-style content blocks:
    [{"type": "text", "text": "..."},
     {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]

Vision backends read the image; text-only backends flatten to just the text.
These helpers keep that translation in one place.
"""
from __future__ import annotations


def text_of(content) -> str:
    """Flatten content (a string, or a list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text", "")))
            elif isinstance(b, str):
                parts.append(b)
        return " ".join(p for p in parts if p)
    return str(content or "")


def images_of(content) -> list:
    """Base64 image payloads (no `data:` prefix) from a content block list."""
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "image_url":
                url = (b.get("image_url") or {}).get("url", "")
                if isinstance(url, str) and ";base64," in url:
                    out.append(url.split(";base64,", 1)[1])
    return out


def has_images(messages) -> bool:
    return any(images_of(m.get("content")) for m in (messages or []) if isinstance(m, dict))


def flatten(messages) -> list:
    """Copy of `messages` with every content flattened to text (for text-only
    backends that can't accept image blocks)."""
    out = []
    for m in messages or []:
        if isinstance(m, dict):
            m = dict(m)
            m["content"] = text_of(m.get("content"))
        out.append(m)
    return out
