# Phase 3 + 4 — Self-improvement (governed) and the bridge

Builds on Phase 2. Two things landed: the **governed self-improvement loop**, and
the **interfaces that make this a shared hub** (MCP bridge + HTTP API).

## Phase 3 — the self-improvement loop (governed)

- **`improvement/feedback.py`** — records a signal per turn (model used, scope,
  reply length, optional explicit score), persisted to `data/feedback.jsonl`.
  `rate()` attaches an explicit 👍/👎; `by_model()` aggregates avg score per model.
- **`improvement/optimizer.py`** — `propose()` aggregates feedback per model and,
  when one reliably wins (≥ `min_samples`), returns a **candidate Policy** that
  routes the default intents to it (never mutates the live policy). `apply()`
  gates the proposal through governance. *Upgrade path: swap `propose` for a DSPy
  **GEPA** loop.*
- **Governance wraps every self-change:**
  - **`governance/guardrails.py`** — fail-closed allow-list; a policy update is
    permitted only within an **impact ceiling** (`max_policy_changes`).
  - **`governance/versioning.py`** — JSON **snapshot/rollback** of the policy
    before any update.
  - **`governance/audit.py`** — append-only **JSONL** log of every change
    (before/after/reason) → `data/audit.jsonl`.
- **`Orchestrator.optimize()`** ties it together: propose → guardrail-gate →
  snapshot → audit → apply in place (the router shares the Policy, so new rules
  take effect immediately). Run it from the CLI with **`:optimize`**; rate the
  last reply with **`:good`** / **`:bad`**.

## Phase 4 — the bridge

- **`interfaces/mcp.py`** — `build_mcp_server()` exposes **`ask`**,
  **`retrieve_memory`**, **`remember`** as MCP tools. *This is the piece that
  makes agi-layer the shared brain your other agents connect to.* Run with
  `AGI_INTERFACE=mcp python main.py` (needs `pip install mcp`).
- **`interfaces/api.py`** — `build_app()` serves `POST /turn`, `GET /memory`,
  `POST /consolidate`, bound to localhost. Run with `AGI_INTERFACE=api python
  main.py` (needs `pip install fastapi uvicorn`).
- **`main.py`** picks the interface via `AGI_INTERFACE` (`cli` default).

## Verify (offline)

```bash
python3 tests/smoke.py     # now 20 checks incl. optimizer, governance, bridges
python3 main.py            # then try :good / :bad / :optimize
```

The MCP/HTTP servers and the DSPy/GEPA upgrade need their deps installed; the
code import-guards cleanly without them so the layer always boots.

## Remaining follow-ups

- Consolidation `promote` / `reconcile` / `decay` stages + APScheduler cron.
- Graph population from the write path (entity/relation extraction).
- DSPy **GEPA** optimizer; Voyager-style skill self-authoring (`skills.author`).
- Memory snapshotting in `versioning` (policy is covered today).
