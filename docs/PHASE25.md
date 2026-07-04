# Phase 25 — Backups (never lose what you built)

Snapshot everything Myro remembers — memory, routines, profile, audit — so you
can't lose it. **Local-first**, with optional encryption and an optional push to
a private GitHub repo.

## Code vs. your data (why updates are safe)

Myro's **code** lives in git. Everything **you build** lives in **`data/`**, which
is **gitignored** — it's never in the repo, never pushed, and never touched when
you update the code. So `git pull` gives you new features while your memories stay
put. (Schema changes are additive/backward-compatible on purpose.) Backups are
about protecting `data/` against disk loss, not about the code.

## What it does (`core/backup.py`)

`run_backup` = **snapshot → (encrypt) → rotate → (push)**:

1. **Snapshot** — archives all of `data/` into
   `<backup_dir>/myro-backup-<stamp>.tar.gz` (default `data/backups`). Point
   `backup_dir` at a **synced folder (OneDrive/Dropbox/Google Drive)** and you get
   off-site backup with nothing else configured.
2. **Encrypt (optional)** — set a passphrase and the archive is encrypted
   (Fernet + PBKDF2, random salt; needs the `cryptography` package), so it's safe
   to store anywhere. Degrades to a plain local snapshot if crypto is unavailable
   — a backup always succeeds.
3. **Rotate** — keeps the last `backup_keep` (default 7).
4. **Push (optional)** — if `backup_git_dir` (a local clone of a **private** backup
   repo) is set, the snapshot is copied there and `git add/commit/push`ed.

`restore(archive, data_dir)` extracts a snapshot back (path-traversal guarded).

## Automatic + on demand

- **`backup` tool** (unattended — it only writes your own data locally by default,
  so it's schedulable and needs no confirmation).
- **`backup` starter routine** ("Nightly backup", suggested `at 02:00`): install
  with `:starters`, then `:schedule backup at 02:00`.
- **`:backup`** in the terminal, and a **"Back up now"** button in the app's
  Settings tab.

## Setup (env)

```bash
# local snapshots to a cloud-synced folder (private, off-site, no GitHub):
export AGI_BACKUP_DIR="$HOME/OneDrive/Myro-backups"
# encrypt them (recommended before anything leaves your machine):
export AGI_BACKUP_PASSPHRASE="a long passphrase you'll remember"
# also push to a PRIVATE GitHub backup repo you cloned locally:
export AGI_BACKUP_GIT_DIR="$HOME/myro-backup-repo"
```

## Privacy

Your memory is personal. A snapshot is **all** of `data/` (all scopes), so if it
leaves your machine — GitHub (even private) or a cloud drive — **encrypt it**.
Local-only snapshots stay on your disk. The `backup` tool never pushes unless you
set `backup_git_dir`.

## Verify

```bash
python3 tests/smoke.py     # 186 checks; section 36 covers backups
```

Section 36 verifies: a snapshot archives the data files; restore round-trips;
rotate keeps only N; `run_backup` makes a local snapshot and doesn't push by
default; the git-push command is correct; encrypt↔decrypt round-trips (when
`cryptography` is present, else skipped); the `backup` tool is registered
unattended; and the nightly-backup starter exists. Also verified against the real
web server — `POST /api/backup` writes an actual snapshot to disk.

## Notes

- The `backup` tool degrades: a broken/absent `cryptography` still yields a plain
  local snapshot (it never fails the whole backup).
- Restore is manual for now (extract the archive into `data/` while Myro is
  stopped); a guided `:restore` is a small follow-up.
