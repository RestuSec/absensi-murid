# 🏫 Sistem Absensi Guru — Yayasan Islam

Sistem absensi guru dengan **Dashboard Web + Absen via QR**.
Mendukung 3 unit: **MI**, **MTs**, **RA**.

---

## 📁 Struktur Project

```
absensi-guru/
├── backend/
│   ├── main.py          ← FastAPI API
│   ├── serve.py         ← Entry point (API + Dashboard)
│   ├── database.py      ← SQLite setup
│   └── requirements.txt
├── dashboard/
│   ├── login.html
│   ├── index.html          ← Dashboard admin (Data Absensi / Guru & QR / Rekap)
│   ├── absen.html          ← Halaman absen web (dibuka lewat scan QR)
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── monitor_bot.py       ← Monitor Keamanan (deteksi aktivitas mencurigakan + laporan)
├── env_loader.py        ← Loader .env tanpa dependency eksternal
├── start_all.bat        ← Launcher proses (Windows)
├── stop_all.bat         ← Stop semua proses
└── .env.example         ← Template konfigurasi (copas jadi .env)
```

---

## 🚀 Cara Install & Jalankan

### 1. Clone / copy folder project

### 2. Install dependency
```bash
cd backend
pip install -r requirements.txt
```
> Wajib dijalankan dari folder `backend` karena ada `requirements.txt` di sana.

### 3. Konfigurasi
```bash
# Di folder root project
cp .env.example .env
# Edit .env, isi SECRET_KEY, BOT_API_KEY, password admin,
# dan PUBLIC_URL (ganti ke IP LAN/server saat diakses dari HP).
```

### 4. Jalankan Backend + Dashboard
```bash
cd backend
python serve.py
```
Dashboard bisa diakses di: **http://localhost:8000**

> **Akses dari HP:** pastikan HP dan komputer di jaringan yang sama, lalu buka
> IP komputer, contoh: **http://192.168.10.21:8000**. Setel `PUBLIC_URL` di
> `.env` ke IP itu supaya QR mengarah ke alamat yang benar.

> Server ini **tidak** otomatis reload. Setelah mengubah kode backend, restart dulu `serve.py`.

### 5. Jalankan Monitor Keamanan (opsional)
```bash
python monitor_bot.py
```
Memantau akses & aktivitas mencurigakan, lalu kirim alert ke admin.

> **Windows:** jalankan `start_all.bat` untuk membuka 2 proses sekaligus
> (backend + dashboard, dan monitor keamanan). Tutup dengan `stop_all.bat`.

---

## 🔐 Akun Admin

Akun admin dibuat otomatis dari `.env` saat server pertama kali jalan:

| Username    | Env var          | Unit |
|-------------|------------------|------|
| `admin_mi`  | `ADMIN_MI_PASS`  | MI   |
| `admin_mts` | `ADMIN_MTS_PASS` | MTs  |
| `admin_ra`  | `ADMIN_RA_PASS`  | RA   |

> **Penting:** Jangan pernah pakai password default / simpan password di file kode.
> Password diambil dari `.env` (`.gitignore` sudah mengecualikannya dari git).

---

## 📱 Alur Guru

1. Admin di **Guru & QR** klik **📱 Tampilkan** → QR muncul
2. Guru scan QR pakai kamera HP → terbuka `absen.html` → isi **✅ Hadir / 📋 Izin / 🏥 Sakit**
3. Hasilnya langsung masuk ke dashboard

---

## 📊 Fitur Dashboard

- ✅ Login per unit (MI / MTs / RA), username+password otomatis tersimpan
- ✅ **Guru & QR**: tambah guru, tampilkan QR, **unduh** QR, **kirim via WhatsApp**, dan **buat token baru** (🔄) kalau QR bocor
- ✅ Ganti tanggal → data langsung ke-load hari itu
- ✅ Statistik: Total, Hadir, Izin, Sakit
- ✅ **Long-press row** untuk masuk mode hapus (pilih satu / select all / hapus)
- ✅ Export Excel (dengan warna status)
- ✅ Dark / Light mode

---

## ⚙️ Ganti Password Admin

Edit file `.env` di root project, lalu restart server:

```env
ADMIN_MI_PASS=password_baru_mi
ADMIN_MTS_PASS=password_baru_mts
ADMIN_RA_PASS=password_baru_ra
```

Server otomatis mendeteksi password baru dan meng-update hash bcrypt di database
saat startup (lihat `seed_admin()` di `backend/database.py`).

---

## 🌐 Deploy ke Server

Saat di-deploy, ubah `PUBLIC_URL` di `.env` ke URL/domain server. Untuk
production, gunakan nginx sebagai reverse proxy ke port 8000.
