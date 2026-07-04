@echo off
rem ============================================================
rem  Myro — double-click to open your assistant in the browser.
rem ============================================================
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
set AGI_INTERFACE=api
echo Starting Myro... your browser will open in a moment.
python main.py
echo.
echo Myro has stopped. Press any key to close.
pause >nul
