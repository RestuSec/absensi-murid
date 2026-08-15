@echo off
setlocal
set PORT=8001
set PUBLIC_URL=https://restusec.my.id
start "" /d "%~dp0backend" cmd /c "python serve.py"