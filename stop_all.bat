@echo off
title Absensi Guru - Stop All
echo Menghentikan semua proses Absensi Guru...
echo.

rem Matikan python yang menjalankan uvicorn serve / monitor_bot.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'serve:app|monitor_bot.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; 'Proses dihentikan.'"

echo.
echo Semua proses sudah berhenti.
timeout /t 3 >nul
