@echo off
rem ============================================================
rem  Myro — ONE-TIME full setup. Double-click this once and it
rem  installs everything (all superpowers + the browser). After
rem  it finishes, just double-click Myro.bat to run.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

echo ============================================================
echo   Myro - full setup (installs everything, one time).
echo   Grab a coffee: the browser download can take a few minutes.
echo ============================================================
echo.

rem 1) Make the private environment (.venv) if it isn't there. Prefer Python
rem    3.12; fall back to whatever Python is available.
if not exist ".venv\Scripts\python.exe" (
    echo Creating a private environment ^(.venv^)...
    py -3.12 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv 2>nul
)
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Couldn't create the environment - Python may not be installed.
    echo Get it from https://python.org/downloads  ^(tick "Add Python to PATH"^),
    echo then double-click this file again.
    pause & exit /b 1
)
set "VPY=.venv\Scripts\python.exe"

rem 2) Install Myro + every superpower in one shot.
echo.
echo Installing Myro and all superpowers ^(this is the long part^)...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -e ".[all]"
if errorlevel 1 (
    echo.
    echo Something went wrong installing the packages. Scroll up to see the
    echo error - copy it to me and I'll help you fix it.
    pause & exit /b 1
)

rem 3) Download the browser Myro uses for real web browsing.
echo.
echo Downloading the browser for web browsing...
"%VPY%" -m playwright install chromium

rem 4) Show a health check so you can see everything is green.
echo.
"%VPY%" doctor.py

echo.
echo ============================================================
echo   All set! From now on, just double-click  Myro.bat  to start.
echo   ^(A local Ollama model or `claude login` gives Myro his brain.^)
echo ============================================================
pause
