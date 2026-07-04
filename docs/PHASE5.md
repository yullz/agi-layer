# Phase 5 — Scheduler, graph auto-population, GEPA-ready optimizer

Follow-ups that make the layer run itself and grow its own graph.

## What landed

- **Background scheduler** (`core/scheduler.py`) — runs `memory.consolidate()`
  (the "sleep" pass) off the hot path on the configured cron. Uses **APScheduler**
  when installed, else a stdlib **threading.Timer** fallback. `main.py` starts it
  automatically for every interface (cli/api/mcp) and stops it on exit.
  `run_now()` triggers a pass manually.
- **Graph auto-population** (`memory/extract.py` + `write_path._update_graph`) —
  every write now extracts entities (heuristic: capitalised tokens, minus common
  words) and links their **co-occurrences** into the knowledge graph, deduped by
  name+scope via `GraphStore.get_or_create_entity` / `relate`. The graph fills
  itself as you talk, so multi-hop retrieval has something to traverse. (Swap the
  heuristic for an NER/LLM extractor for precision.)
- **DSPy GEPA optimizer** (`improvement/gepa_optimizer.py`) — the real upgrade
  path for self-improvement: reflective prompt evolution that beats MIPROv2/RL
  with far fewer rollouts. Import-guarded (`pip install dspy-ai` + a model);
  until then the heuristic `Optimizer` stays the always-available default.

## Verify (offline)

```bash
python3 tests/smoke.py     # now 24 checks incl. scheduler, graph population, GEPA guard
python3 main.py            # consolidation scheduler starts in the background
```

## Turn on the extras

| Feature | Enable |
|---|---|
| Cron-accurate scheduler | `pip install apscheduler` |
| GEPA prompt optimization | `pip install dspy-ai` (+ point `reflection_model` at a model) |

## Remaining follow-ups

- Consolidation `promote` / `reconcile` / `decay` stages (needs owning the
  semantic store, or Mem0 hooks).
- Typed relation extraction for the graph (subject–predicate–object), beyond
  co-occurrence.
- Voyager-style skill self-authoring (`improvement/skills.author`) under the
  sandbox guardrail.
- Memory snapshots in `versioning` (policy is covered today).
