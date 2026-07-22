@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title School ERP - Repair and Start

if not exist "manage.py" (
    echo =====================================================
    echo ERROR: manage.py was not found in this folder.
    echo Put this file inside the main school_erp folder,
    echo where manage.py and requirements.txt are visible.
    echo =====================================================
    pause
    exit /b 1
)

echo =====================================================
echo        SCHOOL ERP - AUTOMATIC REPAIR
echo This may take 5 to 15 minutes the first time.
echo Keep the internet connected.
echo =====================================================
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py"
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo ERROR: Python is not installed or not added to PATH.
    echo Install Python 3.10 or newer, tick Add Python to PATH,
    echo then run this file again.
    pause
    exit /b 1
)

%PY_CMD% --version
%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is required.
    pause
    exit /b 1
)

echo.
echo [1/7] Removing the broken virtual environment...
if exist ".venv" rmdir /S /Q ".venv"
if exist ".venv" (
    echo ERROR: Could not remove .venv.
    echo Close all old School ERP command windows and try again.
    pause
    exit /b 1
)

echo.
echo [2/7] Creating a clean Windows virtual environment...
%PY_CMD% -m venv ".venv"
if errorlevel 1 goto :failed

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto :failed

echo.
echo [3/7] Updating pip...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo.
echo [4/7] Installing Django and ERP packages...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [5/7] Checking Django...
"%VENV_PY%" -c "import django; print('Django installed successfully:', django.get_version())"
if errorlevel 1 goto :failed

if not exist ".env" (
    if exist ".env.example" copy /Y ".env.example" ".env" >nul
)

echo.
echo [6/7] Preparing the database...
"%VENV_PY%" manage.py migrate
if errorlevel 1 goto :failed

"%VENV_PY%" manage.py shell -c "from portal.models import User; import sys; sys.exit(0 if User.objects.exists() else 1)" >nul 2>nul
if errorlevel 1 (
    echo No existing users found. Creating safe demo data...
    "%VENV_PY%" manage.py seed_demo
    if errorlevel 1 goto :failed
) else (
    echo Existing ERP data found. Demo data was not added.
)

echo.
echo [7/7] Starting School ERP...
echo =====================================================
echo Open in Chrome: http://127.0.0.1:8000
echo Login: principal
echo Password: Principal@123
echo Keep this black window open while using the ERP.
echo Press CTRL+C to stop the server.
echo =====================================================
echo.
start "" http://127.0.0.1:8000
"%VENV_PY%" manage.py runserver 127.0.0.1:8000

pause
exit /b 0

:failed
echo.
echo =====================================================
echo REPAIR FAILED.
echo Take a screenshot starting from the first red ERROR line
echo and send it in the chat.
echo =====================================================
pause
exit /b 1
