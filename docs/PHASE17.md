# Phase 17 — Natural language just works (agentic chat)

Until now, tools only fired behind the `:do` prefix — plain messages went to a
chat-only turn that could *talk about* adding a calendar event but never actually
did it. This phase makes the layer decide for itself: **plain natural language
routes through the agent**, so "can you add a calendar event…" takes the action,
while "what's my name?" just answers.

## How it works (`core/agent.py` + `core/orchestrator.py`)

`handle_turn` now assembles the usual warm persona + retrieved memory + history,
then:

- **Capable model connected** (Claude on your plan, local Qwen — anything that
  isn't the offline echo): the turn runs through the new **`Agent.converse()`**
  loop. The model may reply in plain prose (a normal answer) **or** emit a tool
  call; it's told to reach for a tool *only* when you're asking it to DO
  something. It acts, sees the result, and continues until it answers.
- **Offline (echo)**: degrades to the exact plain-generate path as before — the
  layer still runs with zero setup, just without tool-calling.

`converse()` reuses the same governed loop as `:do`: every tool call is audited,
and **gated tools (write/send/act) still require confirmation** — denied
fail-closed when there's no confirm callback. So:

- In the **CLI**, plain messages pass `_cli_confirm`, so a write still prompts
  `⚠ allow calendar_add_event(...)? [y/N]`, and any tool activity is shown
  (`· git_log(n=1) → …`).
- On **HTTP / MCP**, `handle_turn` is called without a confirm callback, so
  read-only tools work but gated writes are denied — a remote caller can't
  silently send mail or edit your calendar.

`:do` stays as an explicit "definitely use tools" shortcut; nothing about
routines, scheduling, or gating changed.

## Before / after

```
# before
you> can you add a calendar event for the dentist tomorrow at 3pm?
layer> Sure — what time works?           (talked about it; did nothing)

# after (capable model)
you> can you add a calendar event for the dentist tomorrow at 3pm?
  ⚠ allow calendar_add_event(title=Dentist, start=2026-07-05 15:00)? [y/N] y
  · calendar_add_event(title=Dentist, start=2026-07-05 15:00) → added 'Dentist' at …
layer> Done — Dentist is on your calendar tomorrow at 3pm.
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 131 checks; section 29 covers auto-routing
```

Section 29 verifies with scripted models + a real `Orchestrator`: plain language
triggers a tool then answers in prose; a plain question stays conversational with
no tool call; a gated tool in a conversational turn is denied without a confirm;
and the offline echo model uses the plain path (no agent routing), so existing
behavior is unchanged.

## Notes

- The decision to act is the model's, guided by the system prompt — a capable
  model rarely over-triggers, and a stray tool call still needs confirmation for
  anything that writes. Reads (search, calendar_upcoming, git_log…) run freely.
- `orchestrator.last_steps` exposes the tool trace of the most recent turn for
  the CLI to display; the return value stays a plain reply string, so the HTTP
  and MCP interfaces are unaffected.
