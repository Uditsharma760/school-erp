@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title School ERP - Same Wi-Fi Mode
set "VENV_PY=%CD%\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo ERP is not installed. Run FIX_AND_START_ERP.bat first.
    pause
    exit /b 1
)
echo =====================================================
echo SAME WI-FI TEST MODE
echo 1. Keep this PC and phone on the same Wi-Fi.
echo 2. In another CMD run: ipconfig
echo 3. Find IPv4 Address, for example 192.168.1.8
echo 4. On phone open: http://YOUR-IP:8000
echo.
echo Windows Firewall may ask for access. Allow Private networks only.
echo This is LAN testing, not secure public internet hosting.
echo Press CTRL+C to stop.
echo =====================================================
set "ALLOWED_HOSTS=*"
"%VENV_PY%" manage.py runserver 0.0.0.0:8000
pause
