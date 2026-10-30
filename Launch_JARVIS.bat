@echo off
:: JARVIS AI Companion - Desktop Launcher
:: Double-click this file to start JARVIS without any terminal window

:: Navigate to this bat file's own directory (works from anywhere, no hardcoded path)
cd /d "%~dp0"

:: Start the companion in background without keeping terminal open
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw main.py
)

exit
