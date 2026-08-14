# start_jumat.ps1 — buka absensi murid via Cloudflare quick tunnel (gratis)
# Jalankan tiap Jumat: tinggal double-click start_jumat.bat
# Proses: stop lama -> buka server(8001) -> buka tunnel -> ambil URL -> update .env -> restart server -> tampilkan URL

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$EnvFile = Join-Path $Root ".env"
$CfExe = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$CfLog = Join-Path $env:TEMP "opencode\cf_jumat.err"
$SrvLog = Join-Path $env:TEMP "opencode\serve_jumat.err"

Write-Host "=== ABSENSI MURID - START ===" -ForegroundColor Cyan

# 1. Stop proses lama
Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*serve.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Write-Host "[1/5] Proses lama dihentikan"

# 2. Buka tunnel dulu biar dapat URL
Start-Process -FilePath $CfExe -ArgumentList "tunnel","--url","http://localhost:8001","--no-autoupdate" -RedirectStandardOutput (Join-Path $env:TEMP "opencode\cf_jumat.out") -RedirectStandardError $CfLog -WindowStyle Hidden

# 3. Tunggu sampai URL trycloudflare muncul (maks 60 dtk)
$url = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $CfLog) {
        $m = Select-String -Path $CfLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($m -and $m.Matches.Value) { $url = $m.Matches.Value; break }
    }
}
if (-not $url) { Write-Host "[GAGAL] Tunnel tidak dapat URL. Cek $CfLog" -ForegroundColor Red; Read-Host "Enter untuk tutup"; exit 1 }
Write-Host "[2/5] Tunnel OK: $url" -ForegroundColor Green

# 4. Update .env (PUBLIC_URL + CORS_ORIGINS) ke URL baru
$lines = Get-Content $EnvFile
$lines = $lines | ForEach-Object {
    if ($_ -like "PUBLIC_URL=*") { "PUBLIC_URL=$url" }
    elseif ($_ -like "CORS_ORIGINS=*") { "CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,$url" }
    else { $_ }
}
Set-Content -Path $EnvFile -Value $lines -Encoding ASCII
Write-Host "[3/5] .env diupdate ke URL baru"

# 5. Buka server (baca .env baru) di port 8001
$env:PORT = "8001"
Start-Process -FilePath "python" -ArgumentList "serve.py" -WorkingDirectory $Backend -RedirectStandardOutput (Join-Path $env:TEMP "opencode\serve_jumat.out") -RedirectStandardError $SrvLog -WindowStyle Hidden
Remove-Item Env:PORT
Start-Sleep -Seconds 5
Write-Host "[4/5] Server dibuka di port 8001"

# 6. Verifikasi
try {
    $r = Invoke-WebRequest -Uri "$url/login" -UseBasicParsing -TimeoutSec 20
    Write-Host "[5/5] Akses publik OK (HTTP $($r.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "[5/5] Akses publik gagal, tapi tunnel mungkin tetap jalan" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "URL PUBLIK ABSENSI: $url/login" -ForegroundColor Cyan
Write-Host "Login: admin_mi/admin_mts/admin_ra + password di .env"
Write-Host ""
Write-Host "PENTING: setelah URL baru, generate ulang QR murid (QR lama hangus)."
Read-Host "Enter untuk menutup jendela ini"
