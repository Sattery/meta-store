@echo off
cd /d "%~dp0"

if not "%~1"=="" goto :params

set /p SCAN_DIR="Input path: "
if "%SCAN_DIR%"=="" set "SCAN_DIR=."
"D:\env\python\miniconda3\python.exe" meta-store.py scan "%SCAN_DIR%"
goto :end

:params
"D:\env\python\miniconda3\python.exe" meta-store.py %*

:end
pause
