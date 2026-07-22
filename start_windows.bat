@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo ERP is not installed yet. Starting automatic setup...
    call FIX_AND_START_ERP.bat
    exit /b %errorlevel%
)
"%VENV_PY%" -c "import django" >nul 2>nul
if errorlevel 1 (
    echo Django is missing. Starting automatic repair...
    call FIX_AND_START_ERP.bat
    exit /b %errorlevel%
)
echo Open in Chrome: http://127.0.0.1:8000
start "" http://127.0.0.1:8000
"%VENV_PY%" manage.py runserver 127.0.0.1:8000
pause
