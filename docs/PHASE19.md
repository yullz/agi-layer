# Phase 19 — Timezone + working hours, so scheduling lines up with your day

Myro now turns your onboarding answers into a **timezone** and a **working-hours
window**, and uses them for scheduled routines — so a daily routine fires at
*your* local wall-clock, not the machine's, and you can schedule things relative
to your workday.

## What it does (`core/profile.py`)

From the onboarding **location** and **hours** answers:

- **`parse_timezone(text)`** → a `tzinfo`. Handles an IANA name (`Europe/Berlin`),
  a UTC offset (`UTC+2`, `+02:00`, `GMT-5`), or a city / abbreviation
  (`Berlin`, `NYC`, `PST`) via a built-in map (word-boundary matched, so `LA`
  doesn't match "Atlanta"). Uses `zoneinfo` for correct DST when available, else a
  fixed offset. Unknown → falls back to the machine's local time.
- **`parse_working_hours(text)`** → `("09:00", "17:00")` from `"9 to 5"`,
  `"9am-6pm"`, `"09:00-18:00"`, `"mornings"`, etc.

These are derived on onboarding, persisted in `data/onboarding.json`, and applied
live to the routine scheduler.

## Scheduling honors your timezone (`core/routines.py`)

`Routines` now carries a `tz`. A daily **`at HH:MM`** routine is evaluated against
*your* local time, and the once-a-day guard resets at *your* midnight — so
`:schedule morning at 08:00` means 8am where you are, wherever the machine runs.

New convenience: **`:schedule <name> at workstart`** (or `workend`) resolves to
your working-hours window, so a routine can literally line up with the start/end
of your day.

## CLI

```
:profile                    your name / timezone / working hours (+ your local time now)
:profile tz Europe/Berlin   override the timezone
:profile hours 9am-6pm      override the working hours
:schedule morning at workstart
```

On first boot the onboarding confirms what it derived:

```
Thanks, Yulian — that gives me a great start, and I'll remember it.
I'll schedule around your timezone (Europe/Berlin), workday 09:00–17:00.
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 146 checks; section 31 covers tz + hours + scheduling
```

Section 31 verifies (deterministically): UTC offsets map to the right wall-clock
(`UTC+2` at epoch 0 → `02:00`), cities map to a timezone, short abbreviations
don't false-match inside words, working hours parse from free text, `derive`
builds the profile, and a daily routine fires at the user's local time in their
timezone. Also verified end-to-end via the CLI: onboarding "Berlin" + "9 to 5"
→ `Europe/Berlin` / `09:00–17:00`, `:profile` shows correct local time, and
`:schedule … at workstart` resolves to `09:00`.

## Notes

- A `timezone` override lives in `config/settings.py` (IANA name, city, or
  `UTC+2`); it wins over the derived value.
- When `zoneinfo`/tzdata isn't present, a city maps to a fixed offset (no DST);
  an explicit IANA name or offset always works.
