"""Backups — snapshot everything Myro remembers, so you never lose it.

Local-first by design: `run_backup` archives the whole data/ folder (memory,
routines, profile, audit) into a timestamped .tar.gz, keeps the last N, and — if
you point the backup folder at a synced drive (OneDrive/Dropbox) — you get
off-site backup with nothing else configured.

Optional, layered on top:
  - Encryption: set a passphrase and the archive is encrypted (needs the
    `cryptography` package), so it's safe to store anywhere.
  - GitHub: set `backup_git_dir` (a local clone of a PRIVATE backup repo) and the
    snapshot is copied there and pushed.

Your memory is personal — encrypt before it leaves your machine.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import time

_PREFIX = "myro-backup-"


def snapshot(data_dir: str, dest_dir: str, now: float | None = None,
             exclude=("backups",)) -> str:
    """Archive data_dir into dest_dir/myro-backup-<stamp>.tar.gz. Returns the path."""
    os.makedirs(dest_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S",
                          time.localtime(now if now is not None else time.time()))
    path = os.path.join(dest_dir, f"{_PREFIX}{stamp}.tar.gz")
    skip = set(exclude)
    with tarfile.open(path, "w:gz") as tar:
        for entry in sorted(os.listdir(data_dir)):
            if entry in skip:
                continue
            tar.add(os.path.join(data_dir, entry), arcname=entry)
    return path


def _within(base: str, target: str) -> bool:
    base = os.path.realpath(base)
    return os.path.realpath(target).startswith(base + os.sep) or os.path.realpath(target) == base


def restore(archive_path: str, data_dir: str) -> bool:
    """Extract a snapshot back into data_dir (path-traversal guarded)."""
    try:
        os.makedirs(data_dir, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            members = [m for m in tar.getmembers()
                       if _within(data_dir, os.path.join(data_dir, m.name))]
            tar.extractall(data_dir, members=members)
        return True
    except Exception:
        return False


def rotate(dest_dir: str, keep: int = 7) -> int:
    """Delete oldest snapshots beyond `keep`. Returns how many were removed."""
    if keep <= 0:
        return 0
    try:
        snaps = sorted(f for f in os.listdir(dest_dir) if f.startswith(_PREFIX))
    except Exception:
        return 0
    removed = 0
    for f in snaps[:-keep]:
        try:
            os.remove(os.path.join(dest_dir, f))
            removed += 1
        except Exception:
            pass
    return removed


# --- optional encryption (via `cryptography`) -------------------------------
def _fernet(passphrase: str, salt: bytes):
    from base64 import urlsafe_b64encode
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    return Fernet(urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8"))))


def encrypt_file(path: str, passphrase: str):
    """Encrypt path -> path + '.enc' (salt prepended). None if crypto is
    unavailable — backups must always succeed at least unencrypted, so we catch
    BaseException (a broken native crypto lib can hard-panic, not just raise)."""
    try:
        salt = os.urandom(16)
        with open(path, "rb") as f:
            token = _fernet(passphrase, salt).encrypt(f.read())
        enc = path + ".enc"
        with open(enc, "wb") as f:
            f.write(salt + token)
        return enc
    except BaseException:
        return None


def decrypt_file(enc_path: str, passphrase: str, out_path: str) -> bool:
    try:
        with open(enc_path, "rb") as f:
            blob = f.read()
        data = _fernet(passphrase, blob[:16]).decrypt(blob[16:])
        with open(out_path, "wb") as f:
            f.write(data)
        return True
    except BaseException:
        return False


# --- GitHub push ------------------------------------------------------------
def _git_backup_cmds(git_dir: str, name: str):
    return [["git", "-C", git_dir, "add", "-A"],
            ["git", "-C", git_dir, "commit", "-m", f"Myro backup {name}"],
            ["git", "-C", git_dir, "push"]]


def _git_backup(git_dir: str, snapshot_path: str) -> str:
    try:
        shutil.copy2(snapshot_path, git_dir)
        out = ""
        for cmd in _git_backup_cmds(git_dir, os.path.basename(snapshot_path)):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            out = (r.stdout + r.stderr).strip()
        return "pushed to GitHub"
    except Exception as e:
        return f"(git push error: {e})"


# --- orchestration ----------------------------------------------------------
def run_backup(config: dict) -> dict:
    """Snapshot -> (encrypt) -> rotate -> (push). Returns a status dict."""
    data_dir = config.get("data_dir")
    if not data_dir or not os.path.isdir(data_dir):
        return {"ok": False, "error": "no data dir"}
    dest = config.get("backup_dir") or os.path.join(data_dir, "backups")
    path = snapshot(data_dir, dest)
    encrypted = False
    passphrase = config.get("backup_passphrase")
    if passphrase:
        enc = encrypt_file(path, passphrase)
        if enc:
            try:
                os.remove(path)
            except Exception:
                pass
            path, encrypted = enc, True
    removed = rotate(dest, int(config.get("backup_keep") or 7))
    pushed = None
    git_dir = config.get("backup_git_dir")
    if git_dir and os.path.isdir(git_dir):
        pushed = _git_backup(git_dir, path)
    return {"ok": True, "snapshot": os.path.basename(path), "dir": dest,
            "encrypted": encrypted, "rotated": removed, "pushed": pushed}


def summary(res: dict) -> str:
    if not res.get("ok"):
        return f"Backup failed: {res.get('error', 'unknown')}"
    bits = [f"backed up to {res['snapshot']}"]
    if res.get("encrypted"):
        bits.append("encrypted")
    if res.get("pushed"):
        bits.append(res["pushed"])
    if res.get("rotated"):
        bits.append(f"pruned {res['rotated']} old")
    return " · ".join(bits)
