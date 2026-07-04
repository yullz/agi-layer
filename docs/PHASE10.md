# Phase 10 — Ingestion, memory control, and a proactive layer

Three additions that move the layer from "remembers our chats" toward "knows me
and reaches out" — all wired through the existing `MemoryStore` facade, so they
inherit scope, privacy, dedup/supersede, and the graph for free.

## 1. Learn from your world, not just chat (`memory/ingest.py`)

`ingest_path(memory, path, scope)` walks a file or folder, reads text files
(skipping binaries/large files/`.git`/`data`/…), and reconciles durable facts
into memory — which also populates the graph. Uses the LLM extractor's new
`extract_from_text` when a local model is up (real facts), else a concise
per-file note offline.

CLI: **`:ingest <path>`** — "Read N files and learned M things." Ingest a
project's docs under that project's scope to teach it from the source.

## 2. Memory control — curate what it knows (facade + CLI)

New `MemoryStore` methods (backed by the native store), so you own your data:

- **`remember(fact, scope)`** — store a fact (reconciled: dedup/supersede) + graph.
- **`forget(query, scope)`** — soft-delete matching memories (archived, not erased).
- **`correct(old, new, scope)`** — supersede the nearest memory (temporal history kept).
- **`provenance(query, scope)`** — the memories behind an answer, with *when*.

CLI: **`:remember`**, **`:forget`**, **`:correct <a> => <b>`**, **`:why <topic>`**
("Here's what that's based on: … (2026-07-04)"). Trust comes from being able to
see, fix, and delete what it knows. MCP's `remember` tool now routes through
`store.remember` too.

## 3. Proactive / active-learning layer (`core/proactive.py`)

The assistant reaches out instead of only answering:

- **Active learning** — `gaps()` detects profile slots it doesn't know (name,
  timezone, focus, working hours, role); **`:learn`** asks one, and your next
  reply is remembered. On startup it gently nudges about one gap.
- **Proactive recall** — **`:briefing`** surfaces your most important/recent
  facts ("what's on my radar for you").

Everything reads through `retrieve`, so proactive recall respects scope + the
privacy filter automatically.

## Verify (offline)

```bash
python3 tests/smoke.py     # 47 checks incl. ingestion, forget/correct/why, proactive gaps
python3 main.py            # try :ingest ./docs, :why projects, :learn, :briefing
```

## Notes / follow-ups
- Offline ingestion stores a per-file note; real per-fact extraction needs a
  local model (`ollama pull qwen3:14b`). PDF/other binary formats are skipped
  (add a parser to extend).
- Connectors (calendar, git, email) and a scheduled proactive briefing are the
  natural next steps — see `docs/REVIEW.md` for the broader backlog.
