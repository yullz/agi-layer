@echo off
rem ============================================================
rem  Myro — double-click to open your assistant in the browser.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set AGI_INTERFACE=api
cd /d "%~dp0"

rem Use the project's virtual environment if one exists.
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo Starting Myro... your browser will open in a moment.
"%PY%" main.py
echo.
echo Myro has stopped. Press any key to close.
pause >nul
