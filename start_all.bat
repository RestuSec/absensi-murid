@echo off
title Absensi Murid - Launcher
setlocal
set PYTHONIOENCODING=utf-8

echo ==========================================
echo   ABSENSI MURID
echo ==========================================
echo.

rem 1. Backend + Dashboard (port 8001) - jalan background di konsol ini
echo [1/2] Start Backend + Dashboard (port 8001)...
cd /d "%~dp0backend"
start /b "" "C:\Users\Suran\AppData\Local\Python\pythoncore-3.14-64\python.exe" serve.py

rem 2. Tunnel Cloudflare (restusec.my.id) - jalan background di konsol ini
echo [2/2] Start Cloudflare Tunnel...
start /b "" "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run absensi

echo.
echo Semua proses dimulai di terminal ini.
echo Dashboard: https://restusec.my.id
echo Local:     http://localhost:8001
echo Terminal ini harus tetap terbuka (proses jalan di sini).
echo Tekan Ctrl+C untuk berhenti semua.