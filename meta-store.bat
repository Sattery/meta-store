@echo off
cd /d "%~dp0"

if not "%~1"=="" goto :params

set /p SCAN_DIR="Input path: "
if "%SCAN_DIR%"=="" set "SCAN_DIR=."
python meta-store.py scan "%SCAN_DIR%"
goto :end

:params
python meta-store.py %*

:end
pause
