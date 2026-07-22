@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Creating venv and installing dependencies...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo.
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Done.
)

start "" ".venv\Scripts\pythonw.exe" meta_store\tray.py
