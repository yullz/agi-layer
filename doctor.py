"""Myro Doctor — a friendly, plain-language health check.

Double-click Doctor.bat (or run ``python doctor.py``) and this tells you what's
installed and working, what's still missing, and the exact command to fix
anything that isn't. It only *looks* — it never installs, changes, or deletes
anything, and it never touches your memories or data.
"""
import importlib.util
import os
import sys
from pathlib import Path


def _utf8() -> None:
    """Best-effort UTF-8 console so check marks render; harmless if it can't."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# Pretty symbols when the console can take them, plain ASCII when it can't, so
# the report is readable even on a bare legacy Windows terminal.
def _supports_unicode() -> bool:
    try:
        "✓ ✗ •".encode(sys.stdout.encoding or "ascii")
        return True
    except Exception:
        return False


_UNI = _supports_unicode()
OK = "✓" if _UNI else "OK"
NO = "✗" if _UNI else "X"
DOT = "•" if _UNI else "-"


def have(module: str) -> bool:
    """True if a package can be imported — without importing it (fast + safe)."""
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def browser_ready() -> bool:
    """The playwright *package* can be installed while the actual Chromium
    *browser* hasn't been downloaded yet. Check for the real browser too."""
    if not have("playwright"):
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
            return bool(path) and os.path.exists(path)
    except Exception:
        return False


def line(ok: bool, label: str, fix: str = "") -> None:
    mark = f" {OK} " if ok else f" {NO} "
    tail = "" if ok else f"   -> {fix}"
    print(f"  [{mark}] {label}{tail}")


def main() -> int:
    _utf8()
    here = Path(__file__).resolve().parent
    fixes: list[str] = []

    print()
    print("=" * 58)
    print("  Myro Health Check")
    print("  (I only look — nothing is installed, changed, or deleted.)")
    print("=" * 58)

    # --- Python itself -----------------------------------------------------
    v = sys.version_info
    print(f"\nPython: {v.major}.{v.minor}.{v.micro}")
    if v < (3, 11):
        print(f"  [{NO}] Too old. Myro needs Python 3.11 or newer.")
        print("       Install 3.12 from python.org (tick 'Add Python to PATH').")
    elif v >= (3, 14):
        print(f"  [{DOT}] Works, but 3.14 is very new — some extras have no ready-made")
        print("       parts for it yet. If an install fails, use Python 3.12.")
    else:
        print(f"  [{OK}] Good version for Myro.")

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print(f"  [{OK if in_venv else DOT}] "
          + ("Running inside a venv (private toolbox) — nice."
             if in_venv else
             "Not in a venv. That's OK, but a .venv keeps things tidy."))

    # --- The essentials (Myro won't run without these) ---------------------
    print("\nEssentials (required to run at all):")
    line(have("yaml"), "Config reader (pyyaml)", 'pip install -e "."')
    line(have("tzdata"), "Timezones (tzdata)", 'pip install -e "."')
    if not (have("yaml") and have("tzdata")):
        fixes.append('pip install -e "."')

    # --- The brain (need at least one for smart replies) -------------------
    print("\nThe brain (need at least ONE for smart answers):")
    sub = have("claude_agent_sdk")
    fro = have("litellm")
    line(sub, "Claude on your Pro/Max plan (subscription)",
         'pip install -e ".[subscription]"')
    line(fro, "Claude/GPT/Gemini via an API key (frontier)",
         'pip install -e ".[frontier]"')
    if not (sub or fro):
        print(f"      [{DOT}] Neither installed — Myro still runs, but only echoes")
        print("           back instead of thinking. Add one when you're ready.")

    # --- Optional superpowers ---------------------------------------------
    print("\nSuperpowers (all optional — add only what you want):")
    serve = have("fastapi") and have("uvicorn")
    line(serve, "Web app / browser chat (serve)", 'pip install -e ".[serve]"')
    if not serve:
        fixes.append('pip install -e ".[serve]"')

    br_pkg = have("playwright")
    br_bin = browser_ready()
    if br_pkg and br_bin:
        line(True, "Real web browsing (browser)")
    elif br_pkg and not br_bin:
        line(False, "Real web browsing — package ok, but Chromium not downloaded",
             "python -m playwright install chromium")
        fixes.append("python -m playwright install chromium")
    else:
        line(False, "Real web browsing (browser)",
             'pip install -e ".[browser]"  then  python -m playwright install chromium')
        fixes.append('pip install -e ".[browser]"')
        fixes.append("python -m playwright install chromium")

    line(have("pyttsx3"), "Voice output — Myro talks (voice)",
         'pip install -e ".[voice]"')
    line(have("speech_recognition"), "Voice input — you talk to Myro (voice-input)",
         'pip install -e ".[voice-input]"')
    line(have("cryptography"), "Encrypted backups (backup)",
         'pip install -e ".[backup]"')
    line(have("apscheduler"), "Precise scheduling (schedule)",
         'pip install -e ".[schedule]"')
    line(have("sentence_transformers"), "Sharper memory search (rerank)",
         'pip install -e ".[rerank]"')

    # --- Your data (reassurance) ------------------------------------------
    print("\nYour memories & data:")
    data = os.environ.get("AGI_DATA_DIR")
    data_dir = Path(data).expanduser() if data else here / "data"
    if data_dir.exists():
        files = sum(1 for _ in data_dir.rglob("*") if _.is_file())
        print(f"  [{OK}] Found your data folder ({data_dir}) with {files} file(s).")
        print("       This is safe — installing features never touches it.")
    else:
        print(f"  [{DOT}] No data folder yet ({data_dir}).")
        print("       Normal before your first chat — Myro makes it when you start.")

    # --- Verdict -----------------------------------------------------------
    print("\n" + "=" * 58)
    essentials_ok = have("yaml") and have("tzdata")
    if not essentials_ok:
        print("  Result: Myro can't start yet — run the essentials fix below.")
    elif not serve:
        print("  Result: Terminal Myro works. The WEB APP needs one more install.")
    else:
        print("  Result: You're good to go! " + ("" if _UNI else "") + "Run:  python main.py")

    if fixes:
        seen, ordered = set(), []
        for f in fixes:
            if f not in seen:
                seen.add(f)
                ordered.append(f)
        print("\n  To fix what's missing, run these in this folder (venv on first):")
        for f in ordered:
            print(f"     {f}")
    print("=" * 58 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
