@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo First run: installing dependencies...
    uv venv
    uv pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Failed! Install uv first, or run manually:
        echo   pip install pystray Pillow
        pause
        exit /b 1
    )
    echo.
)

start "" ".venv\Scripts\pythonw.exe" meta_store\tray.py
