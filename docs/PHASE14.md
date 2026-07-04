# Phase 14 — Interactive browsing + connectors (git / calendar / email)

Two capabilities that let the agent *act* and *reach your real data*: it can now
drive a page (click, fill, log in — with your confirmation), and read your git
repo, calendar, and mailbox — all local-first.

## 1. Interactive browsing (`core/tools.py`)

`browse` reads a page; the new **`browse_do(url, steps)`** *acts* on one. `steps`
is a tiny one-action-per-line DSL:

```
goto https://app.example.com/login
fill #email = me@example.com
fill #password = ...
click text=Sign in
wait .dashboard
read .dashboard
```

Verbs: `goto`, `click`, `fill`/`type`, `select`, `press`, `wait` (ms or
selector), `read` (a selector, or the whole page). Targets are Playwright
selectors — CSS or `text=…`.

**Safety — this is the important part.** Acting on a page can log in, submit
forms, or make purchases, so `browse_do` is **gated** (`unattended=False`): it
requires confirmation in the CLI and is **denied in automations/routines**,
fail-closed. Reading (`browse`, `web_fetch`) stays unattended; only *acting*
needs consent. Same SSRF guard as the other web tools, and it needs Playwright
(same `[browser]` extra) — without it you get a clear "needs Playwright" message.

## 2. Connectors — read your real world (`core/connectors.py`)

Four read-only, `unattended` tools, each reading something **on your machine**
(no credentials, works offline, leaks nothing):

| Tool | Reads | Source |
|---|---|---|
| `git_log` / `git_status` | recent commits / working-tree state | a git repo |
| `calendar_upcoming` | events in the next N days | an `.ics` file |
| `email_recent` | recent message headers | an `mbox` file |

Each takes a `path` argument, and falls back to a configured default
(`git_repo`, `calendar_file`, `mailbox_file` in `config/settings.py`). Because
they're read-only and unattended, routines can use them safely — e.g. a morning
briefing that also reads your calendar.

**`:connectors`** is a health check — it shows which are wired:

```
Connectors (git / calendar / email):
  ✓ git: ok (.)
  · calendar: not configured
  · email: not configured
```

Network-plus-credential sources (CalDAV, IMAP, GitHub API) are deliberate
extensions on top of these local readers — same tool shape, add an adapter.

## CLI

```
:connectors                     status of git / calendar / email
:do what's on my calendar this week
:do summarize my last 5 commits and what's still uncommitted
:do go to <url>, fill the login form, and tell me what the dashboard says
    ⚠ allow browse_do(url=…, steps=…)? [y/N]      ← acting always asks first
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 85 checks; sections 22-23 cover connectors + interactive
python3 main.py            # :connectors, :do summarize my recent commits
```

Sections 22-23 verify with **real reads** (no network): the git connector reads
this repo's actual commits and status; a generated `.ics` lists upcoming events
and excludes past ones; a generated `mbox` yields its messages;
`connector_status` reports correctly; the action DSL parses; and `browse_do` is
gated — denied in an unattended run and blocked by the SSRF guard.

## Notes / follow-ups

- `browse_do` runs a fixed action list; it doesn't yet loop/branch on what it
  reads. Letting the agent read a page then decide the next action (a
  perceive-act loop) is the next step.
- Connectors are local readers. IMAP/CalDAV/GitHub adapters (config-gated, since
  they need credentials + network) slot in behind the same tool names.
- Calendar datetimes without an explicit zone are treated as UTC — fine for
  briefings; wire a tz for exactness.
