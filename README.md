# agi-layer

A local, personal intelligence layer — a persistent memory + multi-model
orchestration hub you run on your own machine. One process that knows you
deeply, never forgets, routes across every model (frontier + local), and
improves the longer you use it.

Read **[ARCHITECTURE.md](./ARCHITECTURE.md)** first — it's the full design and
the reference every stub points back to.

## What's in the box

This is a scaffold. The design-carrying pieces are implemented; the rest are
contract stubs with docstrings detailed enough to hand straight to Claude Code.

**Implemented:**
- `memory/schema.py` — the full data model (every dataclass the system uses)
- `memory/retrieval.py` — the retrieval-and-ranking pipeline (fusion + rerank + budget packing), the highest-leverage code
- `memory/store.py` — the `MemoryStore` facade and its retriever adapters
- `core/orchestrator.py` — the turn loop
- `core/session.py` — working memory
- `main.py` — the composition root that wires everything

**Contract stubs (raise `NotImplementedError` with a spec in the docstring):**
- stores: `episodic`, `semantic`, `graph`, `procedural`
- `memory/write_path.py`, `memory/consolidation.py` (rich contracts)
- `models/*`, `improvement/*`, `governance/*`, `interfaces/*`, `core/router.py`, `core/context_builder.py`

## Layout

```
agi-layer/
├── ARCHITECTURE.md      <- read this first
├── core/                the orchestration core (the bridge)
├── memory/              the spine: schema, stores, write path, retrieval, consolidation
├── models/              frontier + local adapters, embeddings, reranker
├── improvement/         feedback, optimizer, skills, finetune
├── governance/          audit, guardrails, versioning
├── interfaces/          cli, api, mcp
├── config/              settings + models.yaml
├── data/                your memory lives here (gitignored)
└── main.py              composition root
```

## Quickstart

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`python main.py` will raise `NotImplementedError` from the first store it
constructs — expected. Implement the stubs in build order and the same wiring
comes to life.

## Build order

1. **Spine** — implement `episodic` + `semantic` (pick one vector store) + one frontier + one local model. `retrieval.py` already works once the retrievers return candidates.
2. **Prove it learns you** — after ~a week, check retrieval surfaces the right context unprompted.
3. **The loop** — wire `feedback` → `optimizer`, add nightly `consolidation` (start with summarize + decay).
4. **Then** — `graph`, skill self-authoring, `finetune`, and `governance`.

## The bridge

`interfaces/mcp.py` exposes memory + routing as MCP tools, so other agents
connect to this as their shared memory-and-routing hub — that's what makes it
the layer between all your AIs rather than just another assistant.
