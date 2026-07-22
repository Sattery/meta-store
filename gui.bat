@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: installing GUI dependencies...
    uv venv
    uv pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Failed! Install uv first, or run manually:
        echo   pip install customtkinter
        pause
        exit /b 1
    )
    echo.
)
".venv\Scripts\python.exe" meta-store.py gui
