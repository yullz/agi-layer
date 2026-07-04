# Phase 1 — Hybrid memory spine (it boots and remembers)

This phase turns the scaffold into a **running** personal-intelligence layer. A
turn now flows end-to-end and memory persists across sessions. The hard,
error-prone semantic layer (extraction + dedup + supersede) is delegated to
**Mem0** behind the `MemoryStore` facade — the "hybrid" choice — while the raw
episodic log stays ours in SQLite.

## What now runs

- **`python main.py`** boots to a working REPL (previously it crashed in
  `ModelRegistry.__init__` before reaching the prompt). `:scope <name>` switches
  project scope; `exit` quits.
- **Episodic store** (`memory/episodic.py`) — real SQLite + FTS5 (LIKE
  fallback). Append-only source of truth; backs the keyword and recency
  retrievers. This is what makes write→recall real with no LLM.
- **Semantic store** (`memory/semantic.py`) — **Mem0-backed**, degrades
  gracefully: if Mem0 (or its LLM/embedder) isn't configured, it becomes a safe
  no-op and the layer runs on episodic keyword + recency retrieval.
- **Turn loop** — `Router` (rule-based, reachability-aware), `ContextBuilder`
  (OpenAI/LiteLLM/Ollama messages), model adapters, and the write path are all
  wired. `write_path.ingest` hands the exchange to Mem0 for reconcile-on-write.
- **Model layer** — `FrontierModel` (LiteLLM), `LocalModel` (Ollama over stdlib
  HTTP), and a zero-dependency **`EchoModel`** so the loop runs offline. The
  router auto-selects the first *reachable* backend and falls back to echo.
- **Safety** — `Guardrails` now **fails closed** (deny by default) instead of
  raising; the reranker honours its graceful-degradation contract and sets
  `rerank_score` so a reranker's ordering survives the final re-sort.

## Verify it (no services needed)

```bash
python3 tests/smoke.py     # 7 checks: write→recall, full turn loop, persistence
python3 main.py            # interactive REPL (uses the echo backend offline)
```

## Turn on the real intelligence

1. **Frontier generation** — `pip install litellm`, then
   `export ANTHROPIC_API_KEY=...`. The router will prefer Claude for hard
   queries automatically.
2. **Local generation** — run Ollama (`ollama serve`, `ollama pull qwen2.5`).
   The router uses `qwen-local` when it's reachable.
3. **Semantic memory (Mem0)** — `pip install mem0ai`. With `OPENAI_API_KEY` set
   it uses Mem0's defaults; otherwise it targets a local Ollama config
   (`qwen2.5` + `nomic-embed-text`) — see `_default_mem0_config` in
   `memory/semantic.py`. Once available, vector recall joins keyword + recency.

## Next (Phase 2)

- `consolidation.run` — the nightly "sleep" pass (summarize, promote, decay).
- Thread `scope` into `Router.pick` so sensitive scopes force a local model.
- Real `GraphStore` (entities/relations) for multi-hop retrieval.
- Feedback → GEPA optimization loop (`improvement/optimizer.py`).
