# Phase 2 — Differentiators + subscription-powered Claude

Builds on Phase 1. Two tracks landed together: **use your Claude Max
subscription instead of API credits**, and the **"next-level" memory
differentiators**.

## Track A — Claude on your Pro/Max subscription (no API credits)

- **`models/agent_sdk.py`** (`AgentSDKModel`) — calls Claude through the **Claude
  Agent SDK**, which authenticates with your plan (`claude login`), so usage
  draws from your Max subscription instead of metered API tokens. Degrades to
  unavailable if the SDK isn't installed/authed, so the router won't pick it.
- **`config/models.yaml`** — `claude-opus` / `claude-sonnet` now use
  `adapter: agent_sdk` (subscription). A commented `frontier` (API-key) entry is
  kept as an overflow option. The local model is set to **`qwen3:14b`** (fits a
  16GB GPU at Q4).
- **Enable it:** `pip install claude-agent-sdk` then `claude login`. That's it —
  the router prefers Claude for hard/general queries automatically.

## Track B — the differentiators

- **Scope-aware privacy routing** (`core/router.py`) — `Router.pick` now takes
  the active `scope`. A **sensitive scope** (in `Settings.sensitive_scopes`, or
  containing `private/sensitive/health/finance/personal`) is **forced to an
  on-box model** (local Qwen, else the offline echo model) and **never** a
  frontier/subscription model. This is a hard privacy guarantee: sensitive
  memory does not leave the machine.
- **Real knowledge graph** (`memory/graph.py`) — SQLite `entities` + `relations`
  with a bounded multi-hop BFS in `neighbors()`, returning connected facts as
  GRAPH candidates. Superseded relations are skipped (temporal-safe). This is
  what answers "what tools do I use across projects" that vector search can't.
- **Consolidation "sleep" pass** (`memory/consolidation.py`) — `run()` reads new
  episodes since a persisted **watermark**, groups by scope, and writes rollup
  **SUMMARY** items. Uses your local model as the summarizer when available, with
  a graceful extractive fallback. This is the differentiator that makes memory
  get *wiser*, not just bigger. (promote / reconcile / decay are follow-ups.)
- **Reranker wired** (`models/reranker.py`) — lazy local cross-encoder
  (MiniLM by default; swap in **Qwen3-Reranker** for quality) that sets
  `rerank_score`. Now passed into `MemoryStore`; identity passthrough when
  sentence-transformers isn't installed.

## Verify (offline, no services)

```bash
python3 tests/smoke.py     # 13 checks incl. privacy routing, graph, consolidation
python3 main.py            # REPL; :scope health-private forces on-box model
```

## Recommended stack for this machine (RTX 4070 Super 16GB, local-only extraction)

| Slot | Pick | Enable |
|---|---|---|
| Generation (non-sensitive) | Claude via Max plan | `pip install claude-agent-sdk && claude login` |
| Generation (private) + extraction | Qwen3-14B (local) | `ollama pull qwen3:14b` |
| Embedding | nomic-embed-text | `ollama pull nomic-embed-text` |
| Semantic memory | Mem0 (local config) | `pip install mem0ai` |
| Reranker | MiniLM → Qwen3-Reranker | `pip install sentence-transformers` |

## Next (Phase 3+)

- Feedback → **GEPA** optimization of the routing/prompt policy.
- Consolidation `promote` / `reconcile` / `decay` stages + the APScheduler cron.
- Graph population from the write path (entity/relation extraction).
- The **MCP bridge** (`interfaces/mcp.py`) — expose ask/retrieve/remember so
  other agents share this brain. Governance (audit + snapshot/rollback) before
  any self-modification.
