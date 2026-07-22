@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv and installing GUI dependencies...
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

".venv\Scripts\python.exe" meta-store.py gui
