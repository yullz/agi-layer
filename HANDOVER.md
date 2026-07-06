# Myro — Handover for Claude Code

> **Read this first.** This document is written for a Claude Code instance
> picking up the Myro project on the user's local Windows machine. It explains
> what Myro is, how it is built, how to run it, the exact state of the current
> open problem, and the conventions used so far. Nothing here is secret; do not
> add secrets to it.

---

## 0. The 60-second summary

- **Myro** is a **local-first personal AI** ("personal intelligence layer"):
  persistent memory + multi-model routing + a governed agent that can take
  real actions, wrapped in several interfaces (a web app, a terminal REPL, MCP,
  voice, telegram). Everything runs on the user's own machine, bound to
  `localhost`. Nothing leaves the box unless a cloud "brain" is explicitly used.
- It is a **Python 3.11+** project. The package name is `agi-layer`; the app's
  friendly name is **Myro**.
- There is a premium **web UI** ("the command deck") built with **Vite + React
  + TypeScript** living in `ui/`. Its production build is committed at
  `ui/dist/` and is served by the Python backend at `http://127.0.0.1:8765`.
- The user runs it on **Windows** by double-clicking **`Setup.bat`** once, then
  **`Myro.bat`**.
- **The current open problem:** running `Myro.bat` still shows the *old* built-in
  web page instead of the new command deck, even though the new files are
  present. See **Section 5 — START HERE** for the exact state and next step.

---

## 1. Where the code lives (important — there are two repos)

There are **two GitHub repositories with identical current content**:

| Repo | Role |
|------|------|
| `yullz/agi-layer` | Primary development repo. All 38 build phases were developed and merged here. |
| `yullz/My-Model`  | Mirror. The full project was copied here so the user's GitHub Desktop (which tracks **My-Model**) delivers updates. **This is the repo the user's machine pulls.** |

**Why two repos exist:** for a long time the user's machine pulled `My-Model`,
which originally held only an old `agi-layer.zip` snapshot (no app, no `ui/`),
while all real work went to `agi-layer`. Updates never reached the user. This
was fixed by mirroring the entire current project into `My-Model` `main` and
deleting the stale zip. **The user's local folder is
`C:\Users\Windows\Desktop\Myro`, a clone of `My-Model` `main`.**

**Going forward:** the user pulls `My-Model` `main` via GitHub Desktop. If you
push changes, push to whichever repo you are working in and keep the two in
sync when it matters for the user (the user only pulls My-Model). Default branch
is `main` in both.

---

## 2. How to run it (Windows)

Base Python dependencies are tiny (`pyyaml`, `tzdata`). **The web app needs the
`serve` extra** (`fastapi`, `uvicorn`, `mcp`) — it is **not** installed by
default. The one-click setup installs everything needed.

1. **`Setup.bat`** (double-click, one time). It:
   - creates a private virtual environment `.venv`,
   - `pip install --upgrade pip`,
   - `pip install -e ".[all]"` — where `all = serve, browser, voice,
     voice-input, backup, schedule, subscription, frontier` (all light; **no
     torch/ML**),
   - `playwright install chromium` (a few-minute browser download for the
     `browse` tool),
   - runs `doctor.py` (a health check).
2. **`Myro.bat`** (double-click, every time). It sets `AGI_INTERFACE=api`,
   finds Python (prefers `.venv`), verifies `fastapi` is importable (falls back
   to the terminal REPL if not), then runs `python main.py`, which serves the
   app at **`http://127.0.0.1:8765`** and opens the browser.
3. **`Doctor.bat`** — runs the health check (`doctor.py`) any time.

macOS/Linux equivalents: **`setup.sh`** and **`myro.sh`**.

**Do NOT install the heavy extras** `rerank` (sentence-transformers/torch),
`mem0` (chromadb), or `dspy` unless specifically wanted — they are optional and
were a source of confusion. The web UI does not need them.

**Ports/env:**
- `AGI_INTERFACE` = `cli` (default REPL) | `api` (web app) | `mcp` | `telegram`
  | `voice`. `Myro.bat` sets `api`.
- Server: `127.0.0.1:8765` (localhost only).
- `AGI_DATA_DIR` can override the memory location (default is `<project>/data`).

---

## 3. Architecture — how it works

```
main.py                 entrypoint; reads AGI_INTERFACE and dispatches
core/                   orchestrator, agent, tools, memory, brain, backup, session
memory/                 memory store, retrieval, seeding
models/                 model adapters + registry (routing)
governance/             action gating (the "asks-first" safety layer)
improvement/            self-improvement / GEPA optimizer (optional)
interfaces/
  cli.py                terminal REPL (default)
  api.py                FastAPI HTTP layer  <-- serves the web UI + /api/*
  webapi.py             framework-free app logic behind /api/* (tested offline)
  mcp.py, voice.py, telegram.py
config/
  settings.py           paths + tuning; DATA_DIR = ROOT/"data"
  models.yaml           the model registry (which brains exist + defaults)
ui/                     the React "command deck" front-end (see Section 4)
  dist/                 COMMITTED production build the backend serves
data/                   the user's MEMORY (git-ignored; never commit)
doctor.py               health check; Setup.bat runs it at the end
Setup.bat / Myro.bat / Doctor.bat / setup.sh / myro.sh   launchers
```

### 3.1 Memory
- Lives in **`<project>/data/`** (`config/settings.py: DATA_DIR = ROOT/"data"`).
- **`data/` is git-ignored** (along with `*.db`, `*.sqlite*`, `vectors/`,
  `graph/`). Git never reads, overwrites, or deletes it. It is fully portable:
  to move memory between installs, copy the `data` folder.
- `data/brain.json` stores the current brain choice + effort.
- Backups: `core/backup.py` snapshots the whole `data_dir` into a `.tar.gz`.
- **NEVER commit `data/` or any memory artifact.**

### 3.2 Brains / models (`config/models.yaml`)
Adapters:
- `agent_sdk` — Claude via the user's **Pro/Max plan** (needs
  `claude-agent-sdk`, i.e. the `subscription` extra, and `claude login`).
  Registry names: `claude-opus`, `claude-sonnet`.
- `frontier` — Claude/GPT/Gemini via an **API key** (needs `litellm`, the
  `frontier` extra).
- `local` — **Ollama** models, private + always-on. Names: `qwen-local`,
  `vision-local` (auto-used for image turns once pulled).
- `echo` — offline, zero-dependency fallback; runs with no key and no Ollama.
  This is what you get out of the box, so answers look like an echo until a real
  brain is configured.

The app routes by scope/capability; sensitive scopes prefer local models. Fallback
order shown in the UI is roughly **Claude → Ollama → echo**. Brain choice, effort,
and an **Auto** mode are user-switchable (built in an earlier phase).

### 3.3 Governance (the safety model — a core product value)
- **Read-only answers run automatically** (colored **teal** in the UI).
- **Consequential actions ask first** (colored **amber**): the agent surfaces a
  **ConfirmCard**; nothing is written/sent/run until the user confirms.
- Routines run unattended and **fail closed** — a gated action must be
  pre-authorized when the routine is saved, or it stays read-only.
- This teal=safe / amber=asks-first "color law" is visible everywhere in the UI
  and is a deliberate design signature.

---

## 4. The web UI ("command deck") — `ui/`

- **Stack:** Vite 5 + React 18 + TypeScript, plain CSS with design tokens
  (CSS custom properties). Icons: `lucide-react`. Font: JetBrains Mono, bundled
  locally via `@fontsource` (no third-party CDN; fully offline).
- **Six views:** Chat · Voice · Memory · Routines · Connectors · Settings.
  Signature elements: an interactive knowledge **Graph** in Memory, a `⌘K` /
  `Ctrl-K` command palette, a boot sequence, and ConfirmCard gating.
- **The data seam is `ui/src/lib/api.ts`** — *live-with-fallback*:
  - At boot, `initApi()` probes the backend `GET /api/status`.
  - If reachable, methods call **`ui/src/lib/live.ts`** (real `fetch` to
    `/api/*`); on any error they fall back to **`ui/src/lib/mock.ts`**.
  - So the deck shows **real data when the backend serves it, and stays fully
    clickable offline** on sample data. Endpoints the backend doesn't expose
    (graph, timeline, audit) intentionally stay on mock.
- **Build:** `cd ui && npm install && npm run build` → outputs `ui/dist/`.
  **`ui/dist/` is committed** so the app ships ready-to-run with **no Node
  install** on the user's machine. **If you change anything under `ui/src`, you
  must rebuild and commit `ui/dist` or users keep seeing the old build.**
- Vite `base: './'` (relative asset paths), so `ui/dist` is servable from `/`.

---

## 5. START HERE — the current open problem

**Symptom:** the user double-clicks `Myro.bat`, the server starts, but the
browser shows the **old** built-in web page, not the new command deck.

### 5.1 How the backend decides which UI to serve (`interfaces/api.py`)
At the **end** of `build_app` (mounted **last** so `/api/*` and `/turn` win):

```python
_UI_DIST = <project>/ui/dist          # os.path relative to interfaces/api.py
if os.path.isfile(os.path.join(_UI_DIST, "index.html")):
    app.mount("/", StaticFiles(directory=_UI_DIST, html=True), name="deck")   # NEW deck
else:
    # fallback: serve interfaces/static/index.html  (the OLD single-file SPA)
```

So: **if `ui/dist/index.html` exists, the new deck is served; otherwise the old
built-in page.** The old page is a single self-contained HTML file at
`interfaces/static/index.html`. The new deck's `index.html` references
`assets/index-*.js` — that string is the reliable fingerprint that
distinguishes them.

### 5.2 What has already been confirmed on the user's machine
- Folder `C:\Users\Windows\Desktop\Myro` is `My-Model` `main` at the latest
  commit; `interfaces/api.py` and `ui/` are **not** modified there.
- **`Test-Path ui\dist\index.html` → `True`** (the new UI file *is* present).
- `Myro.bat` starts the server successfully ("Myro is running — open
  http://127.0.0.1:8765").
- Working-tree drift (~20 modified backend/doc files, leftover from the user's
  old copy) was cleaned with **`git restore .`** (safe — `data/` untouched).
- The user had tried a manual `pip install -e ".[rerank]"` — unnecessary (heavy
  extra) and it hung only because a quote was left open in PowerShell.

**Conclusion so far:** files are correct and the server is up, yet the old page
shows. That leaves exactly two live hypotheses:
1. **Browser cache / an old tab** is showing a stale page.
2. **An old Myro server is still running on 8765** (or the wrong code is being
   imported) and answers instead of the fresh one.

### 5.3 The exact next diagnostic (ask the *server*, ignore the browser)
With the Myro server running, in a separate PowerShell at the project folder:

```powershell
(iwr http://127.0.0.1:8765/ -UseBasicParsing).Content -match 'assets/index-'
```

- **`True`** → the server *is* serving the new deck; the browser was cached.
  Fix: open an **Incognito** window (`Ctrl+Shift+N`) → `http://127.0.0.1:8765`.
- **`False`** → the server is serving old code. Investigate:
  ```powershell
  .venv\Scripts\python -c "import interfaces.api as a; print(a.__file__)"   # is it the local folder or a stale site-packages install?
  Get-NetTCPConnection -LocalPort 8765 | Select-Object OwningProcess        # who owns the port?
  Get-Process python,pythonw -ErrorAction SilentlyContinue                  # is an old server still alive?
  ```
  Likely fixes if `False`: kill stray python servers
  (`Get-Process python,pythonw | Stop-Process -Force`), confirm 8765 is free,
  then start exactly one fresh server and re-test with `iwr` before opening the
  browser. If `import interfaces.api` points at `site-packages` instead of the
  project folder, a stale non-editable install is shadowing the source — reinstall
  editable (`.venv\Scripts\python -m pip install -e ".[serve]"`) or uninstall the
  stale copy.

**Do not declare it fixed from the browser alone — confirm via `iwr` that the
served HTML contains `assets/index-`.**

---

## 6. Conventions used so far

- **Phase workflow:** each unit of work is a "Phase N": create a branch →
  implement → verify (build/run, ideally drive the real flow) → commit → push →
  open a PR → merge to `main`. The project is at **Phase 38**.
- **Commit trailers** used on this project:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  Claude-Session: <your session URL>
  ```
- **Security (hard rules):**
  - **Never commit `data/`, `.env`, secrets, or API keys.** Run a leak check
    before committing (grep the staged diff for key patterns).
  - `node_modules/`, Python `build/` and root `/dist/` are git-ignored; **but
    `ui/dist/` is intentionally committed** (it ships the built UI). The root
    `/dist/` ignore is anchored so it does not swallow `ui/dist`.
- **Verify before claiming done.** For UI/serving changes, the reliable proof is
  fetching the served HTML (as in 5.3), not just a passing build.

---

## 7. Environment specifics (the user's machine)

- **OS:** Windows 11. Shell shown: **Windows PowerShell** and `cmd`.
- **Project folder:** `C:\Users\Windows\Desktop\Myro` (a clone of `My-Model`).
- **Updates:** GitHub Desktop, pulling `My-Model` `main`.
- The user is **not a developer** — prefer double-click `.bat` flows and
  copy-paste one-liners over multi-step manual tooling. Explain *why*, keep
  steps short, and confirm with a concrete check (e.g. `Test-Path`, `iwr`).
- PowerShell gotcha seen: an unterminated quote (`".[rerank]`) drops PowerShell
  into a `>>` continuation prompt — press **Ctrl+C** to escape it.

---

## 8. Short history (Phases 1–38, high level)

Memory core and retrieval → multi-model routing/adapters → governed agent +
tools → CLI and web interfaces → connectors (git/calendar/email/github, read
mostly, writes gated) → routines/scheduling → backups → brain selection UI
(model/effort/Auto) → attachments + local vision routing → Windows setup
(`Setup.bat`/`Doctor.bat`) → the React **command deck** (Phase 36) → **live
backend wiring** for the deck (Phase 37) → **shipping the pre-built deck +
mirroring the full project into My-Model** (Phase 38). Per-phase notes are in
`docs/PHASE*.md`; `ARCHITECTURE.md`, `MYRO.md`, and `README.md` have more depth.

---

## 9. Immediate next actions for you (local Claude)

1. Resolve **Section 5** — run the `iwr` check and follow the True/False branch
   to get the new command deck actually rendering. Confirm via served HTML.
2. If the server serves old code, find and remove whatever shadows the current
   `interfaces/api.py` (stray process on 8765, or a stale site-packages install).
3. Once the deck renders, help the user set up a real **brain** (either
   `claude login` for their plan, or an Ollama model, or an API key) so Myro
   answers for real instead of echoing.
4. Keep `data/` sacred; keep secrets out of git; rebuild+commit `ui/dist` on any
   UI change.
