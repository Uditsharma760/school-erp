@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title School ERP - Repair

echo =====================================================
echo SCHOOL ERP REPAIR
echo This will remove only the .venv dependency folder.
echo Your database and ERP data will not be deleted.
echo =====================================================
echo.
choice /C YN /N /M "Continue repair? [Y/N]: "
if errorlevel 2 exit /b 0

if exist ".venv" rmdir /S /Q ".venv"
call setup_windows.bat
