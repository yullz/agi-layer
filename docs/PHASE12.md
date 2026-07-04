# Phase 12 — The web, and automation on a clock

Two additions that make the agent (Phase 11) genuinely useful day-to-day: it can
now **reach the web**, and routines can **run themselves on a schedule** instead
of only on demand.

## 1. Browser / web tools (`core/tools.py`)

Two new tools, registered for the agent when `allow_web` is on (default):

- **`web_search(query)`** — top web results as `title — url` lines (via
  DuckDuckGo's HTML endpoint; no API key, no new dependency).
- **`web_fetch(url)`** — fetch an http/https page and return its readable text
  (HTML stripped to prose, capped).

Both are **`unattended`** — reading the public web is a read-only outbound GET,
so automations can use them. Because the network is a real attack surface,
`web_fetch` is hardened:

- **http/https only** — `file://`, `ftp://`, etc. are rejected.
- **SSRF guard** — `localhost`, `*.local`, and any host that *resolves* to a
  private / loopback / link-local / reserved address is blocked, so the agent
  can't be talked into hitting your router or cloud metadata endpoint.
- **Byte cap + 15s timeout**, and every failure degrades to a clean
  `(error: …)` string rather than crashing the loop.

Air-gap it entirely with **`allow_web = False`** (or the env override) — the web
tools simply aren't registered.

## 2. Scheduled routines (`core/routines.py` + `main.py`)

Routines gained a dependency-free schedule, stored per routine:

- **`every_minutes: N`** — run every N minutes;
- **`at: "HH:MM"`** — run once a day at that local time (great for a morning
  briefing).

A minute-tick `Scheduler` (`* * * * *`, APScheduler or the stdlib timer
fallback) calls **`routines.run_due()`**, which fires whatever's due, runs it
**unattended** (so write/exec tools stay denied — safe automation by
construction), and records `last_run` / `last_result`. On restart the schedule
persists; the tick is a cheap no-op when nothing is scheduled.

## CLI

```
:schedule <name> every <N>m   run a saved routine every N minutes
:schedule <name> at <HH:MM>   run it once a day at that time
:schedule <name> off          clear its schedule
:routines                     now shows ⏰ schedule + last result
```

Example:

```
:automate morning = search the web for AI news and summarize the top 3 stories
:schedule morning at 08:00
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 67 checks; section 20 covers web tools + scheduling
python3 main.py            # try :tools, :do search the web for …, :schedule
```

Section 20 verifies (no network): web tools register only when allowed, the SSRF
guard blocks loopback and non-http schemes, HTML reduces to text, search results
parse, and scheduled routines fire exactly when due (interval and daily),
advance, and persist.

## Notes / follow-ups

- `web_search` scrapes DuckDuckGo's HTML; if their markup changes it degrades to
  "(no results)". A pluggable search backend (SearXNG, an API key) is a clean
  extension point.
- `web_fetch` reads text only — no JS execution, forms, or auth. For pages that
  need a real browser, a Playwright-backed tool (Chromium is already available)
  is the next step.
- Scheduling is interval + daily-time; full cron per routine is a small addition
  on top of the same `run_due` tick.
