@echo off
rem ============================================================
rem  Myro Health Check — double-click to see what's installed.
rem  It only looks; it never installs or changes anything.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

rem Use the project's venv Python if it exists, else the py launcher, else python.
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python isn't installed or on PATH.
    echo Install it from https://python.org/downloads  ^(tick "Add Python to PATH"^).
    pause & exit /b 1
)

"%PY%" doctor.py
echo.
echo Press any key to close.
pause >nul
