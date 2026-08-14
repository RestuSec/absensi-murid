@echo off
title Absensi Murid - Stop All
echo Menghentikan semua proses Absensi Murid...
echo.

rem Matikan python yang menjalankan uvicorn serve
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'serve:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; 'Proses dihentikan.'"

echo.
echo Semua proses sudah berhenti.
timeout /t 3 >nul
