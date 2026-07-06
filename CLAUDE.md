# CLAUDE.md — operating context for Myro

**Read `HANDOVER.md` first** for full detail. This file is the quick briefing
Claude Code loads at session start.

## What this is
**Myro** — a local-first personal AI (persistent memory + multi-model routing +
a governed agent). Python 3.11+ (package name `agi-layer`). A React "command
deck" web UI lives in `ui/`; its production build is committed at `ui/dist/` and
served by the Python backend at `http://127.0.0.1:8765`.

## Run it (Windows)
- `Setup.bat` once (creates `.venv`, `pip install -e ".[all]"`, playwright, doctor).
- `Myro.bat` every time (sets `AGI_INTERFACE=api`, runs `python main.py`, opens the browser).
- `Doctor.bat` for a health check. macOS/Linux: `setup.sh` / `myro.sh`.
- The web app needs the `serve` extra (fastapi/uvicorn); base deps alone won't serve it.
- **Do not** install `rerank`/`mem0`/`dspy` (heavy, unnecessary).

## Current open issue (START HERE — see HANDOVER.md §5)
`Myro.bat` still shows the **old** built-in page instead of the new deck, even
though `ui/dist/index.html` exists and the server starts. The backend serves the
deck only if `ui/dist/index.html` exists (else the old `interfaces/static`
page). Files are confirmed present, so the cause is browser cache **or** a stale
server on 8765. Decisive check (server running):
```powershell
(iwr http://127.0.0.1:8765/ -UseBasicParsing).Content -match 'assets/index-'
```
`True` = server is fine, browser cached → open Incognito. `False` = old code
being served → check port owner / stray python / stale install. Confirm the fix
via the served HTML, not the browser.

## Hard rules
- **Never commit `data/` (the user's memory), `.env`, or any secret/API key.** Leak-check staged diffs.
- `node_modules/`, `build/`, root `/dist/` are ignored — **but `ui/dist/` is committed** (ships the built UI).
- **Rebuild + commit `ui/dist` whenever you change `ui/src`**, or users see the old build.
- Two repos with identical content: `yullz/agi-layer` (dev) and `yullz/My-Model`
  (what the user's GitHub Desktop pulls). The user's folder is a clone of
  `My-Model` `main`.
- The user is non-technical — prefer double-click `.bat` flows and short
  copy-paste one-liners; verify with a concrete check.

## Key paths
`main.py` (entry, reads `AGI_INTERFACE`) · `interfaces/api.py` (serves UI + `/api/*`)
· `interfaces/webapi.py` (app logic) · `config/models.yaml` (brains) ·
`config/settings.py` (`DATA_DIR = ROOT/"data"`) · `ui/src/lib/api.ts` (live+mock
data seam) · `ui/dist/` (committed build).
