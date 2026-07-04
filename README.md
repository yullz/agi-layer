# agi-layer

A local-first **personal intelligence layer** — a persistent memory + multi-model
orchestration hub you run on your own machine. The assistant is named **Myro**:
one process that remembers you across sessions, keeps sensitive things on your
box, routes across models (frontier + local), and gets sharper the more you use
it.

It **runs today**, fully offline, with zero external services. Real models and
embeddings light it up further — nothing is required to start.

```bash
python main.py                          # terminal: first boot asks a few questions, then chat
AGI_INTERFACE=api python main.py        # or open the browser app (double-click Myro.bat on Windows)
python tests/smoke.py                   # 192 offline checks prove the whole spine
```

**Windows, zero fuss:** double-click **`Setup.bat`** once (installs everything —
web app, browsing, voice, backups) then **`Myro.bat`** to run. Mac/Linux:
`./setup.sh` then `./myro.sh`. One command for the lot: `pip install -e ".[all]"`.

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
- **Does tasks, not just talk.** Just talk to it — plain natural language ("add
  a calendar event for the dentist tomorrow at 3pm") routes through a governed,
  model-agnostic **agent loop** that decides whether to act or answer, and calls
  **tools** (read files, calc, search memory, **search / fetch / browse the web**
  — including JS-rendered pages and **interactive** click/fill/login via headless
  Chromium, run a command) to actually get things done (`:do <task>` forces the
  tool path) — including a **perceive-act loop** (`browse_agent`)
  that observes a page (text + accessibility tree, and screenshots for vision
  models), decides, clicks, and repeats toward a goal. Write / exec / interactive
  tools are gated (confirm required) and every call is audited;
  **routines** (`:automate` / `:run`, plus **`:starters`** for ready-made ones)
  save tasks and run them unattended, fail-closed — and can run **on a schedule**
  (`:schedule morning at 08:00`).
- **Reads *and acts on* your real world.** Local-first **connectors**
  (`:connectors`) read your **git** repo (log / status), **calendar** (`.ics`
  file or URL), and **email** (`mbox`), plus networked, config-gated **GitHub**
  (commits / issues / PRs) and **IMAP** (headers) — all read-only and unattended.
  And it can **act**, each gated: open a **GitHub issue**, add a **calendar
  event**, **send email** (SMTP).
- **Improves under governance.** Feedback → a routing optimizer (GEPA-ready),
  gated by fail-closed guardrails, snapshot/rollback, and an audit log.
- **Reaches you anywhere — and listens.** **Speaks** replies aloud via local TTS
  (`:voice on`, plus a `speak` tool routines can use), **hears you** via local
  speech-to-text (`:listen`, or fully hands-free with a **wake word** —
  "Hey Myro" — via `AGI_INTERFACE=voice`),
  **pushes to your phone** (ntfy / Telegram / Pushover — the unattended `notify`
  tool, so a scheduled briefing lands on your phone), and lets you **text him**
  from anywhere via a **Telegram** bridge (`AGI_INTERFACE=telegram`, authorized
  chat only, gated writes denied over the wire).
- **Has a real app.** A clean, premium **browser chat app** (`AGI_INTERFACE=api`,
  or double-click `Myro.bat`) — served from your own machine, works offline —
  with chat, voice, memory, routines, connectors, and settings tabs.
- **Backs itself up.** `:backup` (or a nightly routine) snapshots all of `data/`
  locally — point it at a synced drive, encrypt it, or push to a private GitHub
  repo. Your data (`data/`) is gitignored and separate from the code, so updates
  never touch your memories.
- **Is a bridge.** Exposes `ask` / `retrieve_memory` / `remember` over **MCP** so
  your other agents share this brain (`AGI_INTERFACE=mcp`), plus a localhost HTTP
  API.

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
├── interfaces/          cli, api, mcp, telegram, voice (+ wake word)
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
