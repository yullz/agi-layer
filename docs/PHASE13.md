# Phase 13 — A real browser, and routines that work out of the box

Two additions on top of Phase 12: the agent can open a **real browser** for
pages plain fetching can't read, and it ships with **prebuilt starter routines**
so automation is one command away instead of something you have to author.

## 1. `browse` — a real (headless) browser tool (`core/tools.py`)

`web_fetch` reads static HTML; many pages (SPAs, infinite scroll, JS-gated
content) render nothing without JavaScript. The new **`browse(url)`** tool opens
the page in headless **Chromium via Playwright**, lets its JS run, and returns
the rendered text.

- Same **SSRF guard** as `web_fetch` (http/https only; localhost/private/
  loopback blocked, even via DNS resolution) and the same size cap.
- **`unattended`**, so automations can use it.
- **Degrades cleanly.** If Playwright or its browser isn't installed, or a launch
  fails, `browse` falls back to `web_fetch` — it always returns something and
  never crashes the agent loop. (Verified: with Playwright absent it silently
  uses the text fetch.)

Enable the real browser:

```bash
pip install "agi-layer[browser]"   # or: pip install playwright
playwright install chromium
```

The layer still runs fully without it — `browse` just behaves like `web_fetch`
until Chromium is present.

## 2. Prebuilt starter routines (`core/starter_routines.py`)

`:starters` installs ready-made routines (idempotent), so you get value without
authoring anything. They're added **unscheduled** — nothing runs on a clock
until you opt in with `:schedule`, and each stays inside the unattended tool set
(search / browse / read / recall / remember), so they're safe to automate.

| Routine | What it does | Suggested |
|---|---|---|
| **morning** | Top 3 AI/tech stories, one line + link each, saved to memory | `at 08:00` |
| **linkdigest** | Reads `links.txt`, summarizes each URL, remembers a digest | `at 18:00` |
| **recap** | Memory-only "where things stand" on your current work | `every 480m` |

```
:starters                       # install them
:run morning                    # try it now
:schedule morning at 08:00      # opt into the daily run
```

The **inbox-of-links** flow: drop URLs (one per line) into `links.txt`, and
`linkdigest` fetches each, summarizes it, and remembers the digest — ask
"what was in my link digest?" later and it's there, with `:why` provenance.

## Verify (offline)

```bash
python3 tests/smoke.py     # 73 checks; section 21 covers browse + starters
python3 main.py            # :starters, :run morning, :do browse <a JS-heavy url>
```

Section 21 verifies (no network, no browser launch): `browse` registers only
when web is allowed, the SSRF guard blocks loopback before any launch, starters
install idempotently, a named starter carries its task, and starters are
unscheduled by default.

## Notes / follow-ups

- `browse` extracts `body` innerText — it doesn't click, fill forms, or log in
  yet. Interactive browsing (a small action DSL) is the next extension.
- Starter tasks are plain-language prompts the agent executes; edit
  `core/starter_routines.py` to tune them or add your own.
- Chromium download is ~150 MB; that's why `browser` is an opt-in extra, keeping
  the default install tiny and the offline guarantee intact.
