# Phase 21 — Ready-made daily phone routines

Two prebuilt routines that tie Phase 20 together, so a morning briefing and an
end-of-day recap land on your phone with one `:schedule`.

## New starters (`core/starter_routines.py`)

`:starters` now installs, in addition to the earlier ones:

| Routine | What it does | Suggested |
|---|---|---|
| **phone_briefing** | Today's top AI/tech news + your calendar → **push notification** to your phone | `at workstart` |
| **eod_recap** | Your recent commits + what you worked on + what's still open → **push notification** | `at workend` |

They run **unattended** and only use unattended tools (`web_search`,
`calendar_upcoming`, `git_log`, `recall`, `notify`), so they're safe to schedule
— nothing gated, no confirmation needed. `notify` reaches only your own
configured device, so the push is safe by construction.

## Use it

```bash
# one-time: configure a channel (most private: self-hosted ntfy)
export AGI_NTFY_TOPIC=myro-<random>       # then subscribe to it in the ntfy app
```
```
:starters                       # installs phone_briefing + eod_recap (unscheduled)
:run phone_briefing             # try it now — a push should hit your phone
:schedule phone_briefing at workstart    # daily, at your workday start, in your tz
:schedule eod_recap at workend
```

If no notification channel is configured the routine still runs and summarizes;
the `notify` step just reports there's no channel — so it degrades cleanly.

## Verify (offline)

```bash
python3 tests/smoke.py     # 157 checks
```

Section 21 now checks the `phone_briefing` + `eod_recap` starters install (and
stay unscheduled by default); section 32 checks the `notify` tool registers as
unattended only when a channel is configured. The `notify` request-building and
the Telegram bridge are covered by section 32 from Phase 20.

## Notes

- These are plain-language tasks the agent executes; tune them in
  `core/starter_routines.py` or write your own with `:automate` + `:schedule`.
- `at workstart` / `at workend` resolve to your onboarding-derived working hours
  in your timezone (Phase 19), so the briefing lines up with your actual day.
