# Phase 6 — Native semantic memory (the intelligence upgrade)

The biggest lever on "how smart it feels" is memory quality, and the one thing
blocking it was that Mem0 owned the semantic store as a black box. This phase
adds a **semantic store we fully own**, selectable behind the same `MemoryStore`
facade — unlocking the memory intelligence the architecture is built around.

## What this unlocks

- **`memory/semantic_native.py`** (`NativeSemanticStore`, SQLite):
  - **Reconcile-on-write** — `add_turn` extracts candidate facts and, per
    candidate, **dedups a near-duplicate** (reinforce importance instead of
    piling up copies). `supersede()` does temporal updates (write new, retire old
    — never overwrite), so "what did I used to…" stays answerable.
  - **A real forgetting curve** — `touch()` reinforces on retrieval;
    `decay(half_life, cold_threshold)` archives cold items (importance × recency)
    out of the hot set without deleting them.
  - **Working vector retrieval** — exact cosine over the current item set, so the
    read pipeline finally fires on **all four** retrievers (vector + keyword +
    graph + recency), not just keyword/recency.
  - **Embeddings**: uses the injected `Embedder` (sentence-transformers, else
    Ollama) when available; otherwise a **deterministic hashing embedding** keeps
    it fully working offline (weaker vectors, identical mechanics).
- **`models/embeddings.py`** — real `Embedder` (sentence-transformers → Ollama),
  graceful.
- **Consolidation gains real stages** (`memory/consolidation.py`): **promote**
  (mine new episodes for facts live extraction missed and reconcile them) and
  **decay** (archive cold items), on top of summarize.
- **`config/settings.py`** — `semantic_backend: "native"` (default) or `"mem0"`.

## Native vs. Mem0 — you now have both

| | Native (default) | Mem0 |
|---|---|---|
| Control over reconcile/decay/temporal | ✅ full | ⛔ engine-managed |
| Extraction quality | heuristic (LLM-upgradeable) | LLM-backed |
| Setup | zero (works offline) | `pip install mem0ai` + a model |

Switch anytime with `Settings.semantic_backend` — the facade makes it a one-line
change. For maximum intelligence + control, native is the default; Mem0 remains
available for its stronger out-of-the-box extraction.

## Verify (offline)

```bash
python3 tests/smoke.py     # now 28 checks incl. reconcile-dedup, supersede, decay, vector search
```

## To make it excellent on your machine

Give the native store real embeddings (much better semantic recall than the
offline hashing fallback):

```bash
pip install sentence-transformers        # Embedder uses all-MiniLM-L6-v2
# or point Embedder at Ollama: ollama pull nomic-embed-text
```

## Remaining follow-ups

- LLM-driven fact extraction + contradiction detection (drives `supersede` for
  real, beyond dedup).
- Typed relation extraction for the graph (beyond co-occurrence).
- Voyager-style skill self-authoring under the sandbox guardrail.
