# Phase 15 — Perceive-act browsing + networked connectors

Two upgrades to Phase 14: the browser can now **decide as it goes**, and the
connectors can reach **networked sources** (GitHub, IMAP, a published calendar
URL) — not just local files.

## 1. Perceive-act browsing (`core/browser_agent.py`)

`browse_do` runs a fixed script; **`browse_agent(url, goal)`** runs a loop:
**observe** the page (URL + visible text + interactive elements) → ask the model
for the single next action → **act** → observe again → repeat until the goal is
met or the step limit. That handles flows you can't pre-plan (multi-step forms,
"click Next until you find X").

Design that keeps it safe and testable:

- **I/O behind a session interface** (`observe()` / `act()` / `close()`), so the
  loop logic runs offline against a fake session — the Playwright adapter is
  thin. The **SSRF guard runs before any browser launch**.
- **Router-driven**, like the main agent, and exposed as a **gated** tool
  (`unattended=False`): you approve the *session* once, then the pilot acts
  autonomously toward the goal within it. **Denied in unattended automations**,
  fail-closed. Needs Playwright (the `[browser]` extra); without it you get a
  clear message.

```
:do use browse_agent to go to <site>, find the pricing page, and tell me the plans
    ⚠ allow browse_agent(url=…, goal=…)? [y/N]
```

## 2. Networked connectors (`core/connectors.py`)

Local readers gained networked siblings — same tool shape, read-only,
config-gated:

| Tool | Reads | Needs |
|---|---|---|
| `github_recent` | recent commits on `owner/name` | nothing for public repos; `github_token` for private |
| `email_imap` | recent headers over IMAP (BODY.PEEK — never marks seen) | `imap_host` / `imap_user` / `imap_password` |
| `calendar_upcoming` | now also accepts a **published `.ics` URL** (Google/Outlook secret address), fetched through the SSRF guard | — |

`email_imap` is registered only when IMAP is configured; credentials stay in
your config on your machine. Networked GETs reuse the same SSRF guard as the web
tools. `:connectors` now reports all five (git / calendar / email / github /
imap).

Config (in `config/settings.py`): `github_repo`, `github_token`, `imap_host`,
`imap_user`, `imap_password`; `calendar_file` may be a path **or** a URL.

## Verify (offline)

```bash
python3 tests/smoke.py     # 97 checks; sections 24-25 cover both additions
python3 main.py            # :connectors, :do summarize recent commits on <owner/repo>
```

Sections 24-25 verify with no network: GitHub commit JSON parses, a bad repo id
is guarded, a calendar URL is SSRF-blocked, IMAP header formatting is correct and
the connector is config-gated, `connector_status` reports the networked ones, and
the right tools register. The perceive-act loop runs actions then finishes
(driven by a fake session + scripted router), blocks a private URL, and degrades
without Playwright; `browse_agent` registers only with a pilot and is gated.

Also confirmed through `main.build()`: 18 tools wired, `browse_agent` gated and
its SSRF guard fires end-to-end, `github_recent` present and read-only.

## Notes / follow-ups

- `browse_agent` observes text + a flat element list; richer perception
  (roles/ARIA, screenshots for a vision model) would make it more robust.
- IMAP is read-only headers; full body fetch and sending are separate, more
  sensitive capabilities (a send tool would be gated).
- GitHub uses the REST commits endpoint; issues/PRs/Actions are more of the same
  urllib pattern behind new tool names.
