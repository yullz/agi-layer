"""File / folder ingestion — teach the layer from your world, not just chat.

Walk a path, read text files, extract durable facts (via the LLM extractor when
available, else a concise per-file note), and reconcile each into memory (which
also updates the graph). Bounded and best-effort: it never crashes on a bad file,
skips binaries/large files, and respects scope (so you can ingest a project's
docs under that project's scope).
"""
from __future__ import annotations

import os

from core.log import log

_TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".py", ".js", ".ts", ".tsx",
             ".json", ".yaml", ".yml", ".toml", ".csv", ".html", ".log", ".cfg"}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "data", "dist", "build"}


def ingest_path(memory, path, scope=None, extractor=None,
                max_bytes: int = 200_000, max_files: int = 200) -> dict:
    """Ingest a file or directory into `memory`. Returns {files, facts}."""
    files = _collect(str(path), max_files)
    facts = 0
    for f in files:
        text = _read(f, max_bytes)
        if not text:
            continue
        try:
            for fact in _facts_from_doc(text, extractor, os.path.basename(f)):
                memory.remember(fact, scope=scope)
                facts += 1
        except Exception:
            log.warning("ingest failed for %s", f, exc_info=True)
    return {"files": len(files), "facts": facts}


def _collect(path, max_files):
    if os.path.isfile(path):
        return [path] if _texty(path) else []
    if not os.path.isdir(path):
        return []
    out = []
    for root, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for n in sorted(names):
            fp = os.path.join(root, n)
            if _texty(fp):
                out.append(fp)
            if len(out) >= max_files:
                return out
    return out


def _texty(fp):
    return os.path.splitext(fp)[1].lower() in _TEXT_EXT


def _read(fp, max_bytes):
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def _facts_from_doc(text, extractor, fname):
    if (extractor is not None and getattr(extractor, "available", lambda: False)()
            and hasattr(extractor, "extract_from_text")):
        try:
            fs = extractor.extract_from_text(text)
            if fs:
                return fs[:20]
        except Exception:
            log.warning("llm doc extraction failed for %s", fname, exc_info=True)
    # Offline fallback: a concise note from the file's first meaningful lines.
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 12][:4]
    note = " ".join(lines)[:300]
    return [f"From {fname}: {note}"] if note else []
