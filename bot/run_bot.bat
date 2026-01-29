@echo off
REM Run the bot with keep-awake enabled
REM Double-click this file or run from command prompt

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "run_bot.ps1"
pause
