@echo off
rem ============================================================
rem  Myro — double-click to open your assistant in the browser.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set AGI_INTERFACE=api
cd /d "%~dp0"

rem Find Python: the project's venv first, then the Windows `py` launcher
rem (installed by python.org even when PATH isn't set), then plain `python`.
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python isn't installed or on PATH.
    echo Install it from https://python.org/downloads  ^(tick "Add Python to PATH"^).
    pause & exit /b 1
)

rem Make sure the app dependencies are present.
"%PY%" -c "import fastapi" >nul 2>nul
if errorlevel 1 (
    echo First-time setup needed. Run this once in PowerShell, then try again:
    echo    py -3.12 -m venv .venv
    echo    .\.venv\Scripts\Activate.ps1
    echo    pip install -e ".[serve]"
    echo.
    echo Opening the terminal version instead for now...
    set AGI_INTERFACE=cli
)

echo Starting Myro... your browser will open in a moment.
"%PY%" main.py
echo.
echo Myro has stopped. Press any key to close.
pause >nul
