@echo off
:: JARVIS AI Companion - Desktop Launcher
:: Double-click this file to start JARVIS without any terminal window

:: Navigate to the project folder
cd /d "e:\Btech Essentials\JARVIS"

:: Start the companion in background without keeping terminal open
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw main.py
)

exit
