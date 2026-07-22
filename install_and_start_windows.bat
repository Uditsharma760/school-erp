@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -c "import django" >nul 2>nul
if errorlevel 1 (
    call repair_windows.bat
    if errorlevel 1 exit /b 1
)

call start_windows.bat
