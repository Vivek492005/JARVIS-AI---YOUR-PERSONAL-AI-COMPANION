@echo off
setlocal

echo ============================================
echo    JARVIS Installer
echo ============================================
echo.

REM --- Check Python is available ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on this system.
    echo Install Python 3.10 or 3.11 from https://www.python.org/downloads/
    echo IMPORTANT: check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/4] Python found. Checking virtual environment...

REM --- Create venv only if it doesn't already exist ---
if exist ".venv\Scripts\activate.bat" (
    echo       Existing .venv detected, skipping creation.
) else (
    echo       Creating .venv ...
    python -m venv .venv
)

echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies from requirements.txt...
pip install --upgrade pip >nul
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Dependency installation failed. Check the messages above.
    pause
    exit /b 1
)

echo [4/4] Setting up your .env file...
if exist ".env" (
    echo       .env already exists, leaving it untouched.
) else (
    copy .env.example .env >nul
    echo       Created .env from template — remember to add your API keys!
)

echo.
echo ============================================
echo    Setup complete!
echo.
echo    Next steps:
echo    1. Open .env and add your API keys
echo       (HuggingFace, DeepSeek, Rumik)
echo    2. Double-click Launch_JARVIS.bat to start
echo ============================================
pause
