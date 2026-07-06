#!/usr/bin/env bash
# ============================================================
#  Myro — run this to open your assistant in the browser.
#  Mac: you can double-click after `chmod +x myro.sh`, or rename to myro.command
# ============================================================
cd "$(dirname "$0")" || exit 1
[ -f .venv/bin/activate ] && source .venv/bin/activate
export AGI_INTERFACE=api

# Make sure the app dependencies are present; otherwise fall back to the
# terminal REPL instead of crashing (mirrors Myro.bat).
if ! python -c "import fastapi" >/dev/null 2>&1; then
  echo "First-time setup needed — run ./setup.sh once (it installs everything),"
  echo "then run Myro again. Opening the terminal version for now…"
  export AGI_INTERFACE=cli
fi

# The premium "command deck" UI ships pre-built in ui/dist, so it just works.
# If it's ever missing and Node is installed, rebuild it once here.
if [ "$AGI_INTERFACE" = "api" ] && [ ! -f ui/dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Building the Myro deck UI once — this can take a minute…"
    ( cd ui && npm install && npm run build )
  fi
  [ ! -f ui/dist/index.html ] && \
    echo "Note: showing the classic UI. To get the deck: cd ui && npm install && npm run build"
fi

echo "Starting Myro… your browser will open in a moment."
exec python main.py
