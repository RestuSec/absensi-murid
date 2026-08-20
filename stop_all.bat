@echo off
title Absensi Murid - Stop All
echo Menghentikan semua proses Absensi Murid...
echo.

rem Matikan cloudflared tunnel
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; 'Tunnel dihentikan.'"

rem Matikan python yang menjalankan serve.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'serve' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; 'Backend dihentikan.'"

echo.
echo Semua proses sudah berhenti.
timeout /t 3 >nul