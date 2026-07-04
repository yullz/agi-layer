#!/usr/bin/env bash
# ============================================================
#  Myro — ONE-TIME full setup. Run this once and it installs
#  everything (all superpowers + the browser). After it finishes,
#  run ./myro.sh to start.
#     chmod +x setup.sh && ./setup.sh
# ============================================================
set -e
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "  Myro - full setup (installs everything, one time)."
echo "  This can take a few minutes."
echo "============================================================"
echo

# 1) Private environment.
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python isn't installed. Install Python 3.11+ and run this again."
  exit 1
fi
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 2) Install Myro + every superpower in one shot.
echo "Installing Myro and all superpowers (this is the long part)..."
python -m pip install --upgrade pip
python -m pip install -e ".[all]"

# 3) The browser for real web browsing (non-fatal if it can't fetch).
echo "Downloading the browser for web browsing..."
python -m playwright install chromium || echo "(browser download skipped — you can run it later)"

# 4) Health check.
echo
python doctor.py

echo
echo "============================================================"
echo "  All set! Run  ./myro.sh  to start (a local Ollama model or"
echo "  'claude login' gives Myro his brain)."
echo "============================================================"
