# Phase 18 — Meet Myro (identity + first-boot onboarding)

The assistant now has a name — **Myro** — and introduces himself on the first
boot with a short interview, so he knows you from turn one.

## 1. Identity: Myro

- **Persona** (`core/context_builder.py`): the system prompt now opens with
  *"You are Myro, the user's personal intelligence layer…"*, so every model call
  — chat or agentic — carries his name. The name is configurable via
  `assistant_name` in `config/settings.py` (default `Myro`).
- **Interface** (`interfaces/cli.py`): the banner, `:about`, and greetings all
  use his name (`Myro — your personal intelligence layer`).
- The **project / package / bridge** stays `agi-layer` (repo, `pip`, the MCP/HTTP
  service name); *Myro* is the assistant's identity, the "him" you talk to.

## 2. First-boot onboarding (`core/onboarding.py`)

On the first interactive boot, Myro asks **13 introductory questions** (in the
10–15 range) and stores each answer as a durable, global-scope memory — name,
role, current projects, location/timezone, working hours, tools, goals,
interests, communication style, how he can help, important people, things to
avoid, and what you're hoping to get out of working with him.

- Runs **once**: a `data/onboarding.json` marker records completion (and your
  name for the welcome-back greeting). Re-run anytime with **`:onboard`**.
- **Gentle**: press Enter to skip any question, type `stop` to finish early;
  Ctrl-C/EOF ends it cleanly. Whatever you answer is remembered; the rest you can
  fill in later with `:learn`.
- Each answer is stored as a first-person fact (`"My name is …"`,
  `"I'm currently working on …"`), so retrieval and provenance (`:why`) work on
  it like any other memory. The name also updates the live persona so Myro
  addresses you by name immediately.

```
  Myro — your personal intelligence layer
  Hi — I'm Myro. Before we start, can I ask you 13 quick questions
  so I actually know you from the start?
  [1/13] First things first — what should I call you?
  you> Yulian
  ...
  Thanks, Yulian — that gives me a great start, and I'll remember it.
```

On later boots: `Welcome back, Yulian.`

## Verify (offline)

```bash
python3 tests/smoke.py     # 139 checks; section 30 covers identity + onboarding
python3 main.py            # first run walks the interview; second run welcomes back
```

Section 30 verifies: 10–15 questions each with a fact template, skip/stop
handling, an answer stored as retrievable memory, the once-only `done` marker +
name persisting across a restart, and the persona identifying as Myro (and being
renameable).

## Notes

- Onboarding is a CLI (interactive) flow; HTTP/MCP sessions skip it.
- The persona name is the reliable channel for "who am I"; across restarts Myro
  also recalls your name from stored memory even before the welcome-back line.
