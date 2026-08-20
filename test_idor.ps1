# Test IDOR: admin_mi harus TIDAK bisa lihat/hapus data unit lain (MTs/RA)
# Pakai:  powershell -ExecutionPolicy Bypass -File test_idor.ps1
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$DB   = Join-Path $ROOT "backend\absensi.db"
$BASE = "http://localhost:8001"

# cari password admin_mi dari .env
$miPass = (Select-String -Path (Join-Path $ROOT ".env") -Pattern "^ADMIN_MI_PASS=(.+)$").Matches.Groups[1].Value
if (-not $miPass) { Write-Host "ADMIN_MI_PASS tidak ditemukan di .env" -ForegroundColor Red; exit 1 }

function Login($user, $pass) {
  $r = Invoke-WebRequest -Uri "$BASE/api/login" -Method POST `
        -Body "username=$user&password=$pass" `
        -ContentType "application/x-www-form-urlencoded" -UseBasicParsing
  ($r.Content | ConvertFrom-Json).access_token
}

# ── Seed: data milik unit lain (MTs) + materi milik admin_mts ──
$py = @"
import sqlite3
c = sqlite3.connect(r'$DB'); cur = c.cursor()
# murid MTs
cur.execute("SELECT id FROM murid WHERE unit='MTs' LIMIT 1")
row = cur.fetchone()
mid = row[0] if row else None
if not mid:
    cur.execute("INSERT INTO murid (token,nama,kelas,unit,urutan) VALUES ('idor-test-token','TEST MTs','X','MTs',9999)")
    mid = cur.lastrowid
cur.execute("INSERT INTO nilai (murid_id,mapel,nilai,tanggal) VALUES (?,?,?,?)",(mid,'TESTSECRET',100,'2026-01-01'))
nid = cur.lastrowid
cur.execute("INSERT INTO materi (judul,isi,tanggal,created_by) VALUES ('TESTSECRET Materi','x','2026-01-01','admin_mts')")
tid = cur.lastrowid
c.commit(); c.close()
print(f'{mid} {nid} {tid}')
"@
$seed = "$env:TEMP\test_idor_seed.py"; Set-Content -Path $seed -Value $py -Encoding UTF8
$ids = (python $seed).Split(" ") | ForEach-Object { [int]$_ }
Remove-Item $seed -Force
$testMid, $testNid, $testTid = $ids[0], $ids[1], $ids[2]

# ── Tes sebagai admin_mi ──
$tok = Login "admin_mi" $miPass
$h   = @{ Authorization = "Bearer $tok" }
$passCount = 0; $failCount = 0

Write-Host "`n== TES IDOR (login sebagai admin_mi, unit MI) ==" -ForegroundColor Cyan

# 1. GET /api/nilai tidak boleh mengandung TESTSECRET
$list = (Invoke-WebRequest -Uri "$BASE/api/nilai" -Headers $h -UseBasicParsing).Content | ConvertFrom-Json
if ($list.mapel -contains "TESTSECRET") { Write-Host "[FAIL] nilai unit lain terlihat" -ForegroundColor Red; $failCount++ }
else { Write-Host "[PASS] nilai unit lain tidak terlihat" -ForegroundColor Green; $passCount++ }

# 2. DELETE /api/nilai/<milik MTs> harus 404
try {
  Invoke-WebRequest -Uri "$BASE/api/nilai/$testNid" -Method DELETE -Headers $h -UseBasicParsing -ErrorAction Stop | Out-Null
  Write-Host "[FAIL] nilai unit lain bisa dihapus" -ForegroundColor Red; $failCount++
} catch {
  $st = $_.Exception.Response.StatusCode.value__
  if ($st -eq 404) { Write-Host "[PASS] hapus nilai unit lain diblokir (404)" -ForegroundColor Green; $passCount++ }
  else { Write-Host "[FAIL] status tidak terduga: $st" -ForegroundColor Red; $failCount++ }
}

# 3. DELETE /api/materi/<milik admin_mts> harus 404
try {
  Invoke-WebRequest -Uri "$BASE/api/materi/$testTid" -Method DELETE -Headers $h -UseBasicParsing -ErrorAction Stop | Out-Null
  Write-Host "[FAIL] materi admin lain bisa dihapus" -ForegroundColor Red; $failCount++
} catch {
  $st = $_.Exception.Response.StatusCode.value__
  if ($st -eq 404) { Write-Host "[PASS] hapus materi admin lain diblokir (404)" -ForegroundColor Green; $passCount++ }
  else { Write-Host "[FAIL] status tidak terduga: $st" -ForegroundColor Red; $failCount++ }
}

# 4. Regression: admin_mi masih bisa akses nilai unit sendiri (kosong = wajar, yang penting tidak error)
$self = (Invoke-WebRequest -Uri "$BASE/api/nilai" -Headers $h -UseBasicParsing).Content | ConvertFrom-Json
Write-Host "[INFO] nilai unit MI terlihat: $($self.Count) baris" -ForegroundColor Yellow

# ── Bersihkan data uji ──
$pyClean = @"
import sqlite3
c = sqlite3.connect(r'$DB'); cur = c.cursor()
cur.execute("DELETE FROM nilai WHERE mapel='TESTSECRET'")
cur.execute("DELETE FROM materi WHERE judul='TESTSECRET Materi'")
cur.execute("DELETE FROM murid WHERE token='idor-test-token'")
c.commit(); c.close()
"@
$clean = "$env:TEMP\test_idor_clean.py"; Set-Content -Path $clean -Value $pyClean -Encoding UTF8
python $clean; Remove-Item $clean -Force

Write-Host "`nHasil: $passCount PASS, $failCount FAIL" -ForegroundColor $(if ($failCount) { "Red" } else { "Green" })
exit $failCount