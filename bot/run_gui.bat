@echo off
REM Run the GUI app with keep-awake enabled
REM Double-click this file or run from command prompt

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "run_gui.ps1"
pause
