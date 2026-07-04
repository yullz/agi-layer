# agi-layer — architecture

A local, personal intelligence layer: one process that knows you deeply, never
forgets, routes across every model, and improves the longer you use it. It is
**not** research AGI. It is the assistant people actually mean when they say they
want AGI — continuous, personal, and self-improving. Built for a single user,
local-first, on your own hardware.

## What it is / is not

- **Is:** a persistent memory + multi-model orchestration layer you own and run locally.
- **Is not:** a system whose core reasoning bootstraps itself to superintelligence. Improvement here is bounded and real (see *Self-improvement*) — design around that, not around a fantasy.

The intelligence that *grows* does not live in any model's weights (an LLM is
stateless and forgets between calls). It lives in the scaffolding: the memory,
the routing, and the feedback loops. That scaffolding is this repo.

## The five layers

| Layer | Package | Job |
|---|---|---|
| Orchestration core | `core/` | The bridge. Receives input, routes to a model, assembles context, runs a routing policy that improves. |
| Memory spine | `memory/` | Persistent, four-role memory. ~90% of the "it knows me" feeling. |
| Model layer | `models/` | Frontier APIs + local models behind one interface, plus embeddings and a reranker. |
| Self-improvement loop | `improvement/` | Feedback → prompt/routing optimization, self-authored skills, local fine-tuning. |
| Governance | `governance/` | The governor: bounded actions, audit log, snapshot/rollback. Non-optional. |

---

## Memory design (the core of the system)

### The four stores — roles, not necessarily four databases

On a local box you can back most of these with one SQLite file plus a vector index.

- **Episodic** (`memory/episodic.py`) — append-only raw log of every turn: message, tool calls, model, latency, feedback. Plain SQLite (+ FTS5 for keyword search). This is the **source of truth**; append-only, never hard-deleted, everything else is re-derivable from it.
- **Semantic** (`memory/semantic.py`) — atomic "memory items" (distilled facts and summaries) embedded into a vector store (`sqlite-vec` / Chroma / LanceDB). This is what similarity retrieval hits.
- **Graph** (`memory/graph.py`) — entities (people, projects, tools, preferences) and typed relations, e.g. `(You)-[works_on]->(WhaleTrack)`, `(WhaleTrack)-[uses]->(Docker)`. Two SQLite tables (nodes, edges) to start. Answers multi-hop questions vector search can't.
- **Procedural** (`memory/procedural.py`) — learned "how to do X for this user" and demonstrated preferences. (The routing *policy* is separate — it lives in `core/policy.py`.)

Working memory is not a store — it's the in-process `Session` state for the turn in flight.

### Write path (`memory/write_path.py`) — cheap now, smart async

1. **`append_raw`** — write the raw turn to episodic immediately (microseconds, lossless). Never skip this.
2. **`ingest`** (off the hot path) — extract candidate durable facts, then for each one **reconcile before writing**:
   - no match → upsert as new
   - same fact restated → bump the existing item's importance, drop the duplicate
   - contradicts an existing fact → **supersede** (set `superseded_by`, write the new item with `valid_from=now`, keep the old one)
3. Update graph entities/relations (temporal too — supersede, don't delete).

Reconciliation is the single most-skipped step in naive memory systems, and skipping it is why they fill with contradictions. Be **stingy** on extraction: for memory, precision beats recall — a wrong "fact" is worse than a missing one because it gets retrieved confidently later.

### Read path (`memory/retrieval.py`) — this decides whether it feels smart

This module is fully implemented; it's the highest-leverage code in the system. Pipeline:

1. **Gather** from several retrievers in parallel, because none is enough alone:
   - vector similarity (semantic match)
   - keyword/BM25 over episodic + semantic (exact names, IDs, error strings embeddings blur)
   - graph traversal from entities named in the query (connected facts)
   - recency (time-decayed last-N — "what were we just doing")
2. **Fuse** with **Reciprocal Rank Fusion**, not raw-score comparison — a cosine score, a BM25 score, and a graph distance aren't on the same scale; RRF uses only *rank*.
3. **Rerank** the fused list with a cross-encoder (or a cheap LLM pass). Optional and graceful — no reranker just means keep the fused order.
4. **Score** each candidate as `relevance × importance × recency` (tune the weights in `score_final`).
5. **Budget-pack** greedily under a fixed token budget; compress the overflow into a one-line note so the model knows it existed. A silent drop is how the layer "forgets" mid-conversation.

### Consolidation (`memory/consolidation.py`) — the background "sleep," your differentiator

Runs when idle or nightly, off the hot path, on a cheap/local model. Stages (ship them one at a time; start with summarize + decay):

- **summarize** — cluster raw episodes into higher-level notes (session → weekly rollups, hierarchically), stored as `SUMMARY` items.
- **promote** — mine the log for durable facts live extraction missed; safety net for the stingy write path.
- **reconcile** — resolve contradictions, merge duplicate entities, apply temporal reasoning.
- **decay** — recompute importance from access stats; archive cold items out of the hot index (they stay in episodic).
- **re_embed** — if the embedding model changes, re-embed affected items.

This is what turns a pile of logs into memory that gets *wiser*, not just bigger.

### Forgetting and time — the parts almost everyone omits

Memory that only grows becomes noise: retrieval slows and relevance drops. Every `MemoryItem` carries `importance`, `last_accessed`, `access_count`. Effective retrieval weight = `importance × recency × frequency`; cold items get archived out of the hot vector index, never hard-deleted. Treat facts as **temporal**: `valid_from` + supersede-don't-overwrite, so the system answers both "what do I do now" and "what did I used to do" and never destroys history.

### Scoping — matters a lot for parallel projects

Every memory carries a `scope` tag (e.g. `longevity-code`, `whaletrack`, `ocado`). Retrieval filters to the active scope so worlds don't bleed — without it, a question about an Ocado dashboard drags in unrelated facts and the layer feels dumb. Scope is a first-class filter on **both** write and read.

---

## Self-improvement (in order of leverage and honesty)

`improvement/`. What genuinely improves, easiest to hardest:

1. **Memory accumulation** — the biggest lever, trivially real. Gets smarter about *you* every day with zero training. (This is the whole memory spine above.)
2. **Prompt/routing optimization** (`optimizer.py`) — a DSPy-style loop over `(input, context, output, feedback)` proposes better prompts and routing rules. Moderate effort, real gains.
3. **Skill self-authoring** (`skills.py`) — when the layer hits a capability gap, it writes a new tool, sandbox-tests it, and registers it on success. Voyager-style.
4. **Local fine-tuning** (`finetune.py`) — periodic LoRA on accumulated interactions. Real self-improvement of a component; heavy, run weekly/monthly, never on the hot path.

**What does not happen:** the core reasoning bootstrapping itself to superintelligence. Build the four above and you get a system that measurably improves.

Feedback (`feedback.py`) captures both explicit ratings and implicit signal (did the user rephrase, abandon, correct?), which drives both the optimizer and importance boosts for memories that led to good turns.

---

## Governance (`governance/`) — the governor

A system that self-modifies **and** acts on your behalf needs a governor. This is the one place ambition bites if you skip it.

- **audit.py** — append-only log of every self-modification (policy update, new skill, fine-tune swap, memory bulk edit) with before/after and reason. Your black box when behaviour drifts.
- **guardrails.py** — bounded action space: which actions run unattended vs need confirmation, rate/impact ceilings on self-updates, sandbox requirement for self-authored skills.
- **versioning.py** — snapshot + rollback for policy and memory, so a bad self-update or corrupt consolidation run can be reverted.

Version the system's own policy and snapshot memory. "Continuously improve itself" without this is how these projects quietly corrupt themselves.

---

## The two contracts that hold it together

**1. The memory facade** (`memory/store.py`). The core knows exactly three methods:

```python
class MemoryStore:
    def retrieve(self, query, scope, budget_tokens) -> ContextBundle: ...
    def write(self, turn) -> None: ...
    def consolidate(self) -> None: ...
```

Swap SQLite for Postgres, Chroma for LanceDB, add a store — the core never changes. Keep this boundary clean and you can rebuild anything behind it.

**2. The turn loop** (`core/orchestrator.py`) — read → route → assemble → generate → write, with feedback captured and consolidation running out of band. That's the entire spine.

---

## Module map

```
core/          orchestrator, router, context_builder, policy, session
memory/        store (facade), episodic, semantic, graph, procedural,
               write_path, retrieval*, consolidation, schema*
models/        registry, frontier (LiteLLM), local (Ollama), embeddings, reranker
improvement/   feedback, optimizer (DSPy), skills, finetune (LoRA)
governance/    audit, guardrails, versioning
interfaces/    api (FastAPI), cli, mcp
config/        settings, models.yaml
main.py        composition root

(* = fully implemented; the rest are contract stubs)
```

`interfaces/mcp.py` is what makes this the **bridge**: expose memory + routing as MCP tools and other agents (including an OpenClaw-style setup) connect to this as their shared hub.

---

## Build order — prove the loop before boiling the ocean

1. **Spine:** implement `episodic` + `semantic` (one vector store) + one `frontier` model + one `local` model. Every turn writes to episodic; every query retrieves. `retrieval.py` already works once the retrievers return candidates.
2. **Prove it learns you:** after ~a week, confirm retrieval surfaces the right context unprompted. If that feels like magic, the foundation is right.
3. **The loop:** wire `feedback` → `optimizer`, plus nightly `consolidation` (start with summarize + decay).
4. **Then:** `graph`, `skills` self-authoring, `finetune`, and the `governance` layer as self-modification comes online.

---

## Tech choices (all swappable)

| Concern | Default | Alternatives |
|---|---|---|
| Language | Python 3.11+ | — (ML stack is Python-first) |
| Model routing | LiteLLM | OpenRouter |
| Local models | Ollama | vLLM, llama.cpp |
| Vector store | Chroma | sqlite-vec (zero infra), LanceDB |
| Graph | SQLite tables | embedded graph engine (later) |
| Embeddings / rerank | sentence-transformers | provider embeddings |
| Optimization | DSPy | textual-gradient approaches |
| Orchestration control | this repo | LangGraph if flows get complex |
| Scheduler | APScheduler | OS cron / Task Scheduler |

Versions move monthly — pin them when you install.

---

## Implementer notes / gotchas

- **Reconcile on write, or memory rots.** The `find_similar` → insert/supersede/bump branch in `write_path.ingest` is not optional.
- **Retrieval must never crash a turn.** Every retriever failure and the reranker are already isolated in `retrieval.py`; keep it that way as you add stores.
- **Supersede, don't overwrite.** Overwriting a fact destroys history and breaks "what did I used to..." queries.
- **Scope everything.** Untagged memory bleeds across projects and makes the layer feel dumb.
- **Keep sensitive data local.** Anything scoped sensitive routes to a local model — that's the point of local-first, and it's enforced at the router.
- **The facade is sacred.** If the core ever imports a concrete store directly, you've lost the ability to rebuild memory freely. Everything goes through `MemoryStore`.
