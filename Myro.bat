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
    echo First-time setup needed. Double-click  Setup.bat  once - it installs
    echo everything - then run Myro again.
    echo.
    echo Opening the terminal version instead for now...
    set AGI_INTERFACE=cli
)

rem The premium "command deck" UI ships pre-built in ui\dist, so it just works.
rem If it's ever missing AND you have Node installed, rebuild it once here.
if "%AGI_INTERFACE%"=="api" if not exist "ui\dist\index.html" (
    where npm >nul 2>nul && (
        echo Building the Myro deck UI once - this can take a minute...
        pushd ui
        call npm install
        call npm run build
        popd
    )
    if not exist "ui\dist\index.html" (
        echo.
        echo Note: showing the classic UI. To get the new command deck, install
        echo Node.js from https://nodejs.org then run, inside this folder:
        echo     cd ui  ^&^&  npm install  ^&^&  npm run build
        echo.
    )
)

echo Starting Myro... your browser will open in a moment.
"%PY%" main.py
echo.
echo Myro has stopped. Press any key to close.
pause >nul
