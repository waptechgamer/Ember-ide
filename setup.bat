@echo off
REM Ember IDE — Windows setup script (Phase 0)
REM Creates a venv at .\venv, upgrades pip, and installs requirements.txt.
setlocal enableextensions

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found on PATH
    exit /b 1
)

if not exist "venv" (
    echo [setup] Creating virtual environment in .\venv
    python -m venv venv
) else (
    echo [setup] Reusing existing .\venv
)

call "venv\Scripts\activate.bat"

echo [setup] Upgrading pip
python -m pip install --upgrade pip

echo [setup] Installing requirements
python -m pip install -r requirements.txt

echo [setup] Verifying environment
python verify_env.py
