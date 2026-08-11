@echo off
title Absensi Guru - Launcher
setlocal
set PYTHONIOENCODING=utf-8

echo ==========================================
echo   ABSENSI GURU - YAYASAN ISLAM
echo   Membuka 2 terminal proses...
echo ==========================================
echo.

rem 1. Backend + Dashboard (port 8000)
echo [1/2] Start Backend + Dashboard...
start "Backend API :8000" cmd /k "cd /d %~dp0backend && python serve.py"

rem 2. Bot Security Monitor
echo [2/2] Start Bot Security Monitor...
start "Bot Security Monitor" cmd /k "cd /d %~dp0 && python monitor_bot.py"

echo.
echo Semua proses dimulai. Tutup terminal masing-masing untuk berhenti.
echo Dashboard: http://localhost:8000
echo.
timeout /t 5 >nul
