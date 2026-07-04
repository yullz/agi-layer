# agi-layer

A local-first **personal intelligence layer** — a persistent memory + multi-model
orchestration hub you run on your own machine. One process that remembers you
across sessions, keeps sensitive things on your box, routes across models
(frontier + local), and gets sharper the more you use it.

It **runs today**, fully offline, with zero external services. Real models and
embeddings light it up further — nothing is required to start.

```bash
python main.py        # then :seed, then just talk to it
python tests/smoke.py # 42 offline checks prove the whole spine
```

Read **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full design, and
**[docs/SETUP.md](./docs/SETUP.md)** to switch on real models.

## What it does

- **Remembers you.** Every turn is logged (episodic, SQLite+FTS5); durable facts
  are distilled into an owned vector store with **reconcile-on-write** (dedup +
  supersede contradictions), a **forgetting curve** (reinforce + decay), and a
  self-populating **knowledge graph** of typed relations.
- **Retrieves what matters.** Four retrievers (vector + keyword + graph +
  recency) fused with Reciprocal Rank Fusion, reranked, and packed to a token
  budget. Scoped per project, with global/identity facts always available.
- **Keeps secrets local.** Scope-aware routing sends sensitive scopes to an
  on-box model only; sensitive memory is never packed into a prompt bound for a
  cloud model. Extraction, summarization, and skill-authoring all run on-box.
- **Routes across models.** Claude on your Pro/Max **subscription** (via the
  Claude Agent SDK), local **Qwen** via Ollama, and a zero-dependency **echo**
  fallback so it always runs. Auto-selects the first reachable backend and
  degrades gracefully if one fails mid-turn.
- **Does tasks, not just talk.** A governed, model-agnostic **agent loop**
  (`:do <task>`) reasons in steps and calls **tools** (read files, calc, search
  memory, run a command) to actually get things done. Write/exec tools are gated
  (confirm required) and every call is audited; **routines** (`:automate` /
  `:run`) save tasks and run them unattended, fail-closed.
- **Improves under governance.** Feedback → a routing optimizer (GEPA-ready),
  gated by fail-closed guardrails, snapshot/rollback, and an audit log.
- **Is a bridge.** Exposes `ask` / `retrieve_memory` / `remember` over **MCP** so
  your other agents share this brain (`AGI_INTERFACE=mcp`), plus a localhost HTTP
  API (`AGI_INTERFACE=api`).

## Layout

```
agi-layer/
├── ARCHITECTURE.md      the full design
├── docs/                SETUP + per-phase notes + REVIEW (known follow-ups)
├── core/                orchestrator, router (scope-aware), context builder, scheduler
├── memory/              schema, episodic, native vector store, graph, retrieval,
│                        write path, consolidation, extractor, scope, seed
├── models/              agent_sdk (subscription), local (Ollama), frontier (API),
│                        echo, embeddings, reranker, registry
├── improvement/         feedback, optimizer, gepa_optimizer, skills (self-authoring)
├── governance/          audit, guardrails (fail-closed), versioning
├── interfaces/          cli, api, mcp
├── config/              settings + models.yaml
├── data/                your memory lives here (gitignored)
└── main.py              composition root
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e .            # or: pip install -r requirements.txt
python main.py              # REPL — runs on the offline echo model out of the box
```

At the prompt: `:seed` loads what we already know about you, `:memory` shows it,
`:help` lists commands. To turn on real intelligence (Claude on your plan, local
Qwen, real embeddings), see **[docs/SETUP.md](./docs/SETUP.md)**.

## Status

Every architecture layer is implemented and covered by the offline smoke test.
Known follow-ups from the code review live in **[docs/REVIEW.md](./docs/REVIEW.md)**.
The one intentional stub is `improvement/finetune.py` (LoRA, opt-in and heavy).
