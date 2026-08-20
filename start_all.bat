@echo off
title Absensi Murid - Launcher
setlocal
set PYTHONIOENCODING=utf-8

echo ==========================================
echo   ABSENSI MURID - YAYASAN ISLAM
echo ==========================================
echo.

rem 1. Backend + Dashboard (port 8001, dari .env)
echo [1/2] Start Backend + Dashboard (port 8001)...
start "Backend API :8001" cmd /k "cd /d %~dp0backend && python serve.py"

rem 2. Tunnel Cloudflare (restusec.my.id)
echo [2/2] Start Cloudflare Tunnel...
start "Cloudflare Tunnel absensi" "" "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run absensi

echo.
echo Semua proses dimulai.
echo Dashboard: https://restusec.my.id
echo Local:     http://localhost:8001
echo Tutup masing-masing terminal untuk berhenti.
timeout /t 5 >nul