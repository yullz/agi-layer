# Phase 8 — Typed relations, skill self-authoring, and memory seeding

Three additions: the graph now stores *typed* relations, the layer can *write its
own tools*, and its memory is *seeded* with what we already know about you.

## Typed relation extraction

- **`LLMExtractor.extract_relations`** — pulls `[subject, predicate, object]`
  triples (snake_case predicates: `works_on`, `uses`, `lives_in`, …).
- **`write_path._update_graph`** — when the LLM extractor is available, writes
  **typed** relations into the graph (real subject→predicate→object structure);
  falls back to co-occurrence otherwise. Multi-hop recall gets meaningfully
  smarter (e.g. `You —works_on→ WhaleTrack —uses→ Docker`).

## Skill self-authoring (Voyager-style, governed)

- **`improvement/skills.py`** — `author(gap)` has an LLM draft a
  `def skill(payload)` function, then **statically screens** it (no imports / IO
  / network), **builds** it in a restricted-builtins namespace, **sandbox-tests**
  it against a sample input (thread timeout), and **registers** it on success
  (persisted, reloaded on boot). `available()` exposes registered skills as
  tools.
- **Governed + fail-closed** — authoring requires `guardrails.allow('skill_author')`,
  which is **denied by default**; every attempt is audited. The restricted exec
  is a basic guard, not a hardened sandbox — keep authoring off unless you trust
  the model (for real isolation, run skills in a subprocess/container).

## Memory seeding — the layer starts already knowing you

- **`memory/seed.py`** — `seed_memory(memory)` loads durable **facts** (into the
  semantic store) and typed **relations** (into the graph) drawn from our design
  conversations: your projects (The Longevity Code, WhaleTrack, Ocado, Felt &
  Paper), your stack (OpenClaw, Claude, Ollama, Qwen), hardware (Windows, RTX
  4070 Super 16GB), and preferences (local-first, privacy). Run with **`:seed`**
  in the CLI. Edit `SEED_FACTS` / `SEED_RELATIONS` freely — they're yours.

> Honest note: I can't reach your other chats or your Claude account's
> skills/memory — sessions are isolated and there's no tool for it. Seeding is
> the real version of "integrate what you know about me": it plants what we
> established together, and the layer accrues the rest as you use it.

## Verify (offline)

```bash
python3 tests/smoke.py     # 38 checks incl. typed relations, governed skill
                           # authoring (deny-by-default + happy path), seeding
python3 main.py            # then ':seed' -> {'facts': 7, 'relations': 10}
```

## Remaining follow-ups

- Route memory supersedes/bulk edits through `governance/audit`.
- Harden the skill sandbox (subprocess/container isolation).
- Per-scope seeding + a "global" scope always included in retrieval.
