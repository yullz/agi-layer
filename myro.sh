#!/usr/bin/env bash
# ============================================================
#  Myro — run this to open your assistant in the browser.
#  Mac: you can double-click after `chmod +x myro.sh`, or rename to myro.command
# ============================================================
cd "$(dirname "$0")" || exit 1
[ -f .venv/bin/activate ] && source .venv/bin/activate
export AGI_INTERFACE=api
echo "Starting Myro… your browser will open in a moment."
exec python main.py
