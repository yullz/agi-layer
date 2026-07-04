# Phase 7 — LLM-driven extraction + contradiction detection

Upgrades reconcile-on-write from a heuristic into real memory hygiene. This is
the step that keeps memory from rotting into contradictions — and it's what lets
the native store actually **supersede** stale facts, not just dedup.

## What landed

- **`memory/extractor.py`** (`LLMExtractor`):
  - **`extract(user, assistant)`** — an LLM pulls durable facts from a turn as a
    JSON array (stingy: precision over recall). Robust JSON parsing with a
    heuristic fallback.
  - **`judge(new, old)`** — the LLM classifies a new fact against a similar
    existing one: **SAME** (restate), **CONTRADICTS** (update), or **UNRELATED**.
    This is the judgment heuristics can't make.
- **Native store integration** (`memory/semantic_native.py`):
  - `add_turn` uses the LLM extractor when available (heuristic otherwise).
  - `_reconcile` now has three branches: near-identical → **reinforce**;
    moderately similar + LLM says CONTRADICTS → **supersede** (temporal, old kept
    as history); otherwise → **insert**.
  - Gated by `_use_llm` (cached availability probe), so it degrades to the
    heuristic dedup-only path offline with zero cost.
- **Privacy by default** — the extractor runs on the **private (local) model**
  (`registry.default("private")`), so raw turns are distilled on-box.

## Why it matters

> "Naive memory systems accumulate 'I live in Sofia' forty times plus one stale
> contradiction." — the architecture doc.

With Phase 7, when you later say "I moved to Berlin", the layer recognises it
**contradicts** the old fact and supersedes it — the old value is retained
(archived, `superseded_by` set) so "where did I *used to* live" still works,
while current retrieval returns Berlin. That's the difference between memory that
gets wiser and memory that rots.

## Verify (offline)

```bash
python3 tests/smoke.py     # 30 checks; #13 drives extraction + a contradiction
                           # supersede via a scripted stub model (deterministic)
```

## To activate real extraction

It turns on automatically once the local model is reachable:

```bash
ollama pull qwen3:14b      # the private/extraction model
python main.py             # build() reports semantic._use_llm = True when up
```

## Remaining follow-ups

- Audit memory supersedes (route bulk memory edits through `governance/audit`).
- Typed relation extraction for the graph (subject–predicate–object).
- Voyager-style skill self-authoring under the sandbox guardrail.
