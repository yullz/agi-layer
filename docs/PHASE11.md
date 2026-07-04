# Phase 11 — Agent execution layer (tools, automations, routines)

This is the phase that gives the layer *hands*. Until now it could remember,
reason, and route; now it can **do** — read files, run a calculation, search its
own memory, run a command — by reasoning in steps and calling tools. That's the
capability OpenClaw exists to provide, built natively so it inherits our memory,
privacy routing, and governance instead of bolting them on.

## 1. Tools — the things it can actually do (`core/tools.py`)

A tiny registry of `Tool`s. Each declares whether it's **`unattended`** (safe to
run without asking) or not:

- **Unattended:** `now`, `calc` (AST-sandboxed arithmetic — no `eval`),
  `list_dir`, `read_file`, and — when memory is wired — `recall` (search what it
  knows) and `remember` (save a durable fact).
- **Gated** (`unattended=False`): `write_file`, `run_shell`. These write or
  execute, so they require confirmation and are denied outright in automation.

`build_default_tools(memory)` assembles the set; the registry is trivially
extensible — add a `Tool(name, description, func, params, unattended)` and it
shows up to the agent and in `:tools`.

## 2. The agent loop — governed and model-agnostic (`core/agent.py`)

`Agent(router, tools, audit).run(task, scope, confirm)` runs a step loop:

1. Route the task to a model (scope-aware — a sensitive scope stays on-box).
2. Ask the model for **exactly one JSON object** per step: either
   `{"tool": "...", "args": {...}}` or `{"final": "..."}`.
3. Execute the tool, feed the result back, repeat until a final answer or the
   step limit.

Two deliberate design choices:

- **Prompt-based, not vendor tool-calling.** The loop works identically across
  Claude (on your subscription), a local Qwen, or the offline echo model — no
  backend lock-in. `_parse_call` tolerates models that wrap JSON in prose.
- **Fail-closed governance.** Every tool call is audited. A gated tool runs only
  if `confirm(tool, args)` returns True; with no confirm it's denied. So the
  same loop is safe whether a human is watching or not.

Returns `{"answer", "steps"}` where `steps` is the full tool-call trace — you
always see what it did.

## 3. Routines — save a task, run it later (`core/routines.py`)

`Routines(path, agent)` persists named `(task, scope)` pairs as JSON and runs
them **unattended** (`confirm=None`) — so a routine can read, search, and
compute, but write/exec tools are denied by construction. Safe automation by
default; a scheduler can call `run(name)` later without a human in the loop.

## CLI

```
:do <task>            let me do a task using my tools (gated tools ask first)
:tools                list the tools I can use
:automate <n> = <t>   save task <t> as a routine named <n>
:routines             list saved routines
:run <name>           run a saved routine (unattended)
```

`:do` prints each step (`· calc(expression=6*7) → 42`) then the answer, and
prompts `⚠ allow run_shell(...)? [y/N]` before anything that writes or executes.

## Wiring

`main.build()` constructs the `Router` first, then `tools =
build_default_tools(memory)`, `agent = Agent(router, tools, audit=audit)`, and
`routines = Routines(data/routines.json, agent)`, attaching them to the
orchestrator. Nothing else changed — the turn loop is untouched; this is a new
capability alongside it.

## Verify (offline)

```bash
python3 tests/smoke.py     # 55 checks; section 19 covers the agent + routines
python3 main.py            # try :tools, :do read_file for ./README.md, :automate
```

Section 19 verifies: the agent calls a tool then answers, a gated tool is denied
without confirmation, tool calls are audited, and routines add/run/persist.

## Do I still need OpenClaw?

For task execution, no — this subsumes the routing-plus-hands role, and does it
with your memory and privacy guarantees attached. OpenClaw stays complementary
only for capabilities we haven't built (e.g. a specific connector or sandbox it
already ships). The honest gaps here, tracked in `docs/REVIEW.md`:

- Tools run in-process — no OS-level sandbox yet (the `run_shell`/`write_file`
  gate + fail-closed automation are the current containment).
- No built-in browser/HTTP or calendar/email tools yet — they're just more
  `Tool`s to register.
- Routines are on-demand; wiring them to the existing scheduler for true
  time-based automation is the natural next step.
