# Phase 16 — Richer browser perception + connector write-actions

Two upgrades: the browser pilot *sees* the page better (accessibility tree +
optional screenshots for vision models), and connectors can *act* (create a
GitHub issue, add a calendar event, send an email) — every action gated.

## 1. Richer perception (`core/browser_agent.py`)

Each step the pilot now observes more than raw text:

- **Accessibility tree** — `_flatten_ax` turns Playwright's
  `page.accessibility.snapshot()` into compact `role "name"` lines (buttons,
  textboxes, links…). That semantic skeleton is what a model reasons over far
  more reliably than a DOM dump.
- **Vision (optional)** — when the routed model advertises `supports_vision`,
  the pilot attaches a **screenshot** (base64 PNG) and `_build_messages` sends a
  multimodal user turn (text + image). For any non-vision backend it stays plain
  text — **a model never receives an image it can't handle.** The screenshot is
  only captured when a vision model is active (no wasted work otherwise).

The perception helpers (`_flatten_ax`, `_format_observation`, `_build_messages`)
are pure functions, so the Playwright adapter stays thin and the logic is
unit-tested offline.

## 2. Connector actions (`core/connectors.py`)

New read + write connectors, registered in `core/tools.py`:

| Tool | Kind | Notes |
|---|---|---|
| `github_issues` / `github_prs` | read (unattended) | open issues / PRs on `owner/name` |
| `github_create_issue` | **write (gated)** | opens an issue; needs `github_token` |
| `calendar_add_event` | **write (gated)** | appends a VEVENT to a local `.ics` |
| `email_send` | **write (gated)** | SMTP send; registered only when SMTP configured |

**Gating is the safety spine.** Every tool that changes the world —
`calendar_add_event`, `github_create_issue`, `email_send`, plus the earlier
`write_file` / `run_shell` / `browse_do` / `browse_agent` — is `unattended=False`:
it requires a confirm callback and is **denied in unattended automations**,
fail-closed. Reads stay unattended and automation-safe. The full split is 7 gated
/ 15 unattended across 22 tools.

Networked writes reuse the same defensive posture: the GitHub POST goes to a
fixed API host with a `Bearer` token that never appears in returned/error
strings; SMTP uses STARTTLS then login and always `quit`s; the calendar writer
refuses a URL target (writes only to a local path).

Config (`config/settings.py`): `github_token` (unlocks issue creation),
`smtp_host` / `smtp_user` / `smtp_password` / `smtp_from`.

## CLI

```
:connectors                     now also reports github / imap / smtp
:do open an issue on yullz/agi-layer titled "flaky test" describing …
    ⚠ allow github_create_issue(...)? [y/N]      ← every write asks first
:do add a calendar event "Dentist" tomorrow at 15:00
:do email me@example.com a summary of today's commits
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 127 checks; sections 26-28 cover both additions + hardening
```

Section 26 (writes): `calendar_add_event` writes a `.ics` and it reads back
(real round-trip); the GitHub POST request is built correctly (endpoint / Bearer
/ JSON body); issues-vs-PRs filtering is correct; the MIME message carries the
right headers + body; every write tool is gated; a write connector is **denied in
an unattended run**; SMTP/issue creation are config/token-gated. Section 27
(perception): the accessibility tree flattens correctly, the observation includes
URL/roles/elements, `_build_messages` is text-only for non-vision and multimodal
for vision, and the pilot captures a screenshot only for a vision model.

## Adversarial review + hardening (section 28)

This phase was put through an adversarial multi-lens review (GitHub-REST /
SMTP-MIME / calendar / security / perception / coverage) with independent
verification of every finding. All confirmed findings were fixed and pinned with
tests:

- **SSRF (high):** in-session `goto` navigation (in `browse_do` and the pilot) is
  now re-validated by `_safe_url`, so a public entry page — or a prompt-injection
  string — can't steer a navigation to `localhost` / a private host / `file://`.
  Redirects are re-validated too (`_GuardedRedirect`), closing the redirect-to-
  private-host bypass on every outbound fetch.
- **GitHub:** `github_issues` over-fetches (per_page clamped to 100) so PR
  filtering can't starve the result down to zero on an active repo.
- **SMTP:** port 465 now uses `SMTP_SSL` (TLS-on-connect); cleanup never masks the
  real error. `smtp_port` is configurable.
- **Calendar:** all line-breaks in a title are collapsed (no more `\r` data loss);
  output is a proper VCALENDAR envelope with CRLF endings and RFC 5545 escaping;
  inserts are line-anchored; the UID keys on start+end and adds are idempotent.
- **Vision:** the image part is emitted in OpenAI/LiteLLM `image_url` (data-URI)
  form so a vision backend actually receives it.
- **Coverage:** positive issue-filter test and a `_flatten_ax` cap test added.

## Notes / follow-ups

- Vision requires a vision-capable model adapter to set `supports_vision`; the
  plumbing and text fallback are in place regardless.
- `browse_agent` observes text + accessibility roles; screenshots to a vision
  model are the richer channel when one is configured.
