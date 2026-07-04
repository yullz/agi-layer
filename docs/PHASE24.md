# Phase 24 — The Myro app (a premium local web UI)

A clean, premium chat app for Myro that runs in your browser — **fully local**
(served from your own machine over localhost, works offline). No more terminal
for everyday chatting.

## Open it

```bash
AGI_INTERFACE=api python main.py      # or just double-click Myro.bat (Windows)
```
Your browser opens to `http://127.0.0.1:8765`. That's your computer talking to
itself — nothing goes to the internet unless you use a cloud brain or the web
tools.

## What's in the app

A single-page app (`interfaces/static/index.html`, self-contained, no CDNs) with
a sidebar and five views:

- **Chat** — message bubbles, a "typing…" indicator, and **inline tool activity**
  (every tool Myro uses is shown; blocked/gated actions show a 🔒). A **🎤 talk**
  button (browser speech-to-text) and a **🔊 speak** toggle (browser text-to-
  speech) — voice with *nothing to install*. An **Actions** toggle: on, Myro can
  write/send/run (everything shown + audited); off, he's read-only.
- **Memory** — search what he remembers, and tell him new things to keep.
- **Routines** — create, run, and **schedule** routines (`at 08:00`,
  `every 30m`, `at workstart`); one-click **install starters**.
- **Connectors** — live status of git / calendar / email / GitHub, and the full
  tool list (⚡ safe vs 🔒 gated).
- **Settings** — your name, timezone, and working hours (drives scheduling);
  model status; light/dark theme.

Premium touches: gradient avatar, soft shadows, rounded cards, smooth
transitions, light + dark themes, responsive (works on a phone browser too).

## How it's built (and tested)

- **`interfaces/webapi.py`** — a framework-free `WebApp` class: every method
  returns plain dicts (chat, status, memory, profile, connectors, tools,
  routines, starters). This is the app's real logic, so it's **tested offline
  without any web server**.
- **`interfaces/api.py`** — the thin FastAPI layer: serves the page at `/` and
  maps `/api/*` to the `WebApp` methods. `serve()` auto-opens your browser.
- **`Myro.bat` / `myro.sh`** — one-click launchers (activate the venv, start the
  app, open the browser).

Conversation continuity: the browser keeps a session id (localStorage), so your
chat has memory of the exchange; the server keeps one `Session` per id.

## Safety

Chat runs through the same `handle_turn`, so the gate holds. The **Actions**
toggle maps to the confirm callback: on → gated tools run (and are shown +
audited); off → gated tools are denied. Nothing is hidden — every action Myro
takes appears as a chip in the conversation.

## Verify

```bash
python3 tests/smoke.py     # 178 checks; section 35 covers the app backend
pip install -e ".[serve]" && AGI_INTERFACE=api python main.py   # run it for real
```

Section 35 verifies the `WebApp` handlers end-to-end offline: chat returns a
reply with tool steps, status/memory/profile/connectors/tools/routines all work,
`schedule at workstart` resolves to the derived workday, read-only mode denies
gated actions, and the page ships the chat UI. It was also run against a **real
FastAPI server** (TestClient) — GET `/` serves the page and every `/api/*`
endpoint responds correctly.

> This test caught a real bug: `from __future__ import annotations` made FastAPI
> resolve the endpoint body models as strings against module globals (where the
> locally-defined models don't exist), so it treated the JSON body as a query
> param and every POST 422'd. Removing the future import from `api.py` fixed it.

## Notes / follow-ups

- The app runs while your PC is on (same as the terminal) — it's local, not cloud.
- Native-window wrapper (pywebview) and a packaged `Myro.exe` are the natural
  next steps once you've lived with the app.
- The app's mic/speaker use the **browser's** speech engines (convenient, no
  install); the server-side local Whisper/pyttsx3 remain for the terminal/voice
  interface.
