@echo off
title Absensi Murid - Launcher
setlocal
set PYTHONIOENCODING=utf-8

echo ==========================================
echo   ABSENSI MURID - YAYASAN ISLAM
echo   Membuka 1 proses terminal...
echo ==========================================
echo.

rem 1. Backend + Dashboard (port 8000)
echo [1/1] Start Backend + Dashboard...
start "Backend API :8000" cmd /k "cd /d %~dp0backend && python serve.py"

echo.
echo Semua proses dimulai. Tutup terminal masing-masing untuk berhenti.
echo Dashboard: http://localhost:8000
echo.
timeout /t 5 >nul