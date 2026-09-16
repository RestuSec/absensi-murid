import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from time import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
from env_loader import load_env
load_env()

from fastapi import FastAPI, HTTPException, Depends, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.hash import bcrypt
from pydantic import BaseModel
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import io

from database import get_conn, init_db, seed_admin, new_token
from auth_seed import (
    generate_seed_phrase, build_mapping, hash_seed, verify_seed,
    generate_recovery_key, hash_recovery_key, verify_recovery_key,
    generate_challenge, WORDLIST
)
from database import (
    get_admin_seed_data, get_all_admin_seed_data, clear_admin_seed, setup_seed_and_key, mark_seed_verified
)

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM  = "HS256"
TOKEN_EXP_HOURS = 8

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY belum di-set di .env")

_INSECURE_KEYS = {"secret", "changeme", "your_secret_here", "password", "abc123", "", "none"}
if SECRET_KEY.strip().lower() in _INSECURE_KEYS:
    raise RuntimeError("SECRET_KEY di .env terlalu lemah! Ganti dengan string acak panjang (>=32 karakter)")

VALID_UNITS = ("MI", "MTs", "RA", "ALL")
VALID_STATUS = ("Hadir", "Izin", "Sakit")

LOGIN_MAX_ATTEMPTS = 5
LOGIN_MAX_ATTEMPTS_IP = 10
LOGIN_WINDOW_SEC = 60

# â”€â”€ Excel formula injection guard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")

def excel_safe(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIX):
        return "'" + value
    return value

# â”€â”€ App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(title="Absensi Murid API", docs_url=None, redoc_url=None, openapi_url=None)

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def force_https(request: Request, call_next):
    proto = request.headers.get("x-forwarded-proto")
    if proto and proto.split(",")[0].strip().lower() != "https":
        return RedirectResponse(request.url.replace(scheme="https"), status_code=301)
    return await call_next(request)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: https://maps.googleapis.com https://*.googleapis.com https://*.gstatic.com; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self' https://*.googleapis.com; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), "
        "payment=(), usb=(), "
        "fullscreen=(self), interest-cohort=()"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    return response

# â”€â”€ JWT Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXP_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token tidak valid atau expired")

    username = payload.get("sub")
    unit     = payload.get("unit")
    if not username or not unit:
        raise HTTPException(status_code=401, detail="Token tidak valid atau expired")

    # Validasi unit terhadap database agar admin tidak bisa escalate unit
    # (mis. admin_mi memalsukan unit=ALL / MTs lewat token).
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT unit FROM admin WHERE username = ?", (username,))
    row  = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Token tidak valid atau expired")

    db_unit = row["unit"]
    if unit != db_unit and db_unit != "ALL":
        raise HTTPException(status_code=403, detail="Unit tidak sesuai dengan akun")

    payload["unit"] = db_unit
    return payload

def require_verified(payload: dict = Depends(verify_token)) -> dict:
    """Akses data dashboard wajib melewati verifikasi seed terlebih dahulu."""
    from database import is_seed_verified
    if not is_seed_verified(payload["sub"]):
        raise HTTPException(status_code=403, detail="Seed belum diverifikasi. Verifikasi dulu di /verify")
    return payload

_login_attempts = defaultdict(list)
_login_ip_attempts = defaultdict(list)

def check_login_attempts(request: Request, username: str):
    now = time()
    ip  = request.client.host

    if len(_login_attempts) > 2000:
        cutoff = now - LOGIN_WINDOW_SEC
        for d in (_login_attempts, _login_ip_attempts):
            for k in [k for k, v in d.items() if not v or v[-1] < cutoff]:
                del d[k]

    key = f"{ip}:{username}"
    _login_attempts[key] = [t for t in _login_attempts[key] if now - t < LOGIN_WINDOW_SEC]
    if len(_login_attempts[key]) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login. Coba lagi nanti.")

    _login_ip_attempts[ip] = [t for t in _login_ip_attempts[ip] if now - t < LOGIN_WINDOW_SEC]
    if len(_login_ip_attempts[ip]) >= LOGIN_MAX_ATTEMPTS_IP:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login. Coba lagi nanti.")

    return ip, key

# â”€â”€ Rate limit absen QR (per token + IP) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ABSEB_MAX_PER_MIN = 5
_absen_attempts = defaultdict(list)

def check_absen_rate_limit(request: Request, token: str):
    now  = time()
    ip   = request.client.host
    key  = f"{ip}:{token}"
    _absen_attempts[key] = [t for t in _absen_attempts[key] if now - t < 60]
    if len(_absen_attempts[key]) >= ABSEB_MAX_PER_MIN:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan absen. Tunggu sebentar.")
    _absen_attempts[key].append(now)
    if len(_absen_attempts) > 5000:
        cutoff = now - 60
        for k in [k for k, v in _absen_attempts.items() if not v or v[-1] < cutoff]:
            del _absen_attempts[k]

# â”€â”€ Startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.on_event("startup")
def startup():
    init_db()
    seed_admin()

# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.post("/api/login")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    ip, key = check_login_attempts(request, form.username)

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM admin WHERE username = ?", (form.username,))
    admin = cur.fetchone()
    conn.close()

    # ponytail: dummy hash biar waktu verifikasi seragam â€” user yang tidak ada
    # tetap jalan bcrypt sehingga attacker tidak bisa bedakan via timing.
    DUMMY = "$2b$12$vt5g/54OZcsrT9MsRc4W2u88bwcOYvHv6FNb1Rx/f88r9Z5zzPDAW"
    pwhash = admin["password_hash"] if admin else DUMMY
    if not admin or not bcrypt.verify(form.password, pwhash):
        _login_attempts[key].append(time())
        _login_ip_attempts[ip].append(time())
        raise HTTPException(status_code=401, detail="Username atau password salah")

    _login_attempts.pop(key, None)
    _login_ip_attempts.pop(ip, None)
    token = create_token({"sub": admin["username"], "unit": admin["unit"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "unit": admin["unit"],
        "username": admin["username"],
        "must_change_password": bool(admin["must_change_password"]),
    }

@app.post("/api/admin/change-password")
def change_password(data: dict, payload: dict = Depends(verify_token)):
    """Ganti password sendiri. Wajib saat must_change_password = 1."""
    old_pw  = data.get("old_password", "")
    new_pw1 = data.get("new_password", "")
    new_pw2 = data.get("new_password2", "")
    if len(new_pw1) < 8:
        raise HTTPException(400, "Password baru minimal 8 karakter.")
    if new_pw1 != new_pw2:
        raise HTTPException(400, "Konfirmasi password tidak sama.")
    weak = {"admin", "password", "123456", "changeme", "12345", "qwerty", "password123", "admin123"}
    if new_pw1.strip().lower() in weak:
        raise HTTPException(400, "Password baru terlalu lemah.")
    if new_pw1 == old_pw:
        raise HTTPException(400, "Password baru harus berbeda dari yang lama.")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM admin WHERE username = ?", (payload["sub"],))
    row = cur.fetchone()
    if not row or not bcrypt.verify(old_pw, row["password_hash"]):
        conn.close()
        raise HTTPException(401, "Password lama salah.")
    new_hash = bcrypt.hash(new_pw1)
    cur.execute(
        "UPDATE admin SET password_hash = ?, must_change_password = 0 WHERE username = ?",
        (new_hash, payload["sub"]),
    )
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/me")
def me(payload: dict = Depends(verify_token)):
    return {"username": payload["sub"], "unit": payload["unit"]}

# â”€â”€ Admin: kelola murid + QR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class MuridIn(BaseModel):
    nama: str
    kelas: str
    unit: str
    urutan: int = 0

@app.get("/api/murid")
def list_murid(payload: dict = Depends(require_verified)):
    conn = get_conn()
    cur  = conn.cursor()
    if payload["unit"] == "ALL":
        cur.execute("SELECT id, nama, kelas, unit, urutan, token FROM murid ORDER BY urutan, nama")
    else:
        cur.execute("SELECT id, nama, kelas, unit, urutan, token FROM murid WHERE unit = ? ORDER BY urutan, nama",
                    (payload["unit"],))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/murid")
def create_murid(data: MuridIn, payload: dict = Depends(require_verified)):
    data.unit = payload["unit"] if payload["unit"] != "ALL" else data.unit
    if data.unit not in VALID_UNITS or data.unit == "ALL":
        raise HTTPException(status_code=400, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO murid (nama, kelas, unit, urutan, token) VALUES (?, ?, ?, ?, ?)",
            (data.nama, data.kelas, data.unit, data.urutan, new_token()))
        conn.commit()
        mid = cur.lastrowid
    except Exception:
        raise HTTPException(status_code=400, detail="Data tidak valid")
    finally:
        conn.close()
    return {"ok": True, "id": mid, "token": None}

@app.delete("/api/murid/{murid_id}")
def delete_murid(murid_id: int, payload: dict = Depends(require_verified)):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM murid WHERE id = ? AND (unit = ? OR ? = 'ALL')",
        (murid_id, payload["unit"], payload["unit"]),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Murid tidak ditemukan")
    return {"ok": True, "deleted": deleted}

@app.post("/api/murid/{murid_id}/reset-token")
def reset_murid_token(murid_id: int, payload: dict = Depends(require_verified)):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE murid SET token = ? WHERE id = ? AND (unit = ? OR ? = 'ALL')",
        (new_token(), murid_id, payload["unit"], payload["unit"]),
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Murid tidak ditemukan")
    return {"ok": True}

@app.get("/api/murid/{murid_id}/qr")
def murid_qr(murid_id: int, payload: dict = Depends(require_verified)):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    from PIL import Image
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT token FROM murid WHERE id = ? AND (unit = ? OR ? = 'ALL')",
        (murid_id, payload["unit"], payload["unit"]),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Murid tidak ditemukan")
    url = f"{os.getenv('PUBLIC_URL', 'http://localhost:8000')}/absen?t={row['token']}"
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Logo di atas latar putih solid. kotak ~1/3 lebar QR.
    # ponytail: error-correction H cuma tahan ~30% area tertutup; gedein lagi = gagal scan.
    logo_path = os.path.join(os.path.dirname(__file__), "dashboard", "static", "img", "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        pad = img.size[0] // 3
        logo.thumbnail((int(pad * 0.8), int(pad * 0.8)))

        box = Image.new("RGBA", (pad, pad), (255, 255, 255, 255))
        pos = ((img.size[0] - pad) // 2, (img.size[1] - pad) // 2)
        box.paste(logo, ((pad - logo.width) // 2, (pad - logo.height) // 2), logo)
        img.paste(box, pos)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

# â”€â”€ Halaman absen publik: lookup token â†’ identitas murid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/absen/info/{token}")
def absen_info(token: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT id, nama, kelas, unit, urutan FROM murid WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="QR tidak valid")
    return dict(row)

# â”€â”€ Absen QR (web form) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.post("/api/absen-web")
async def absen_web(
    request: Request,
    token: str    = Form(...),
    status:  str  = Form(...),
    latitude:  Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
):
    # ponytail: QR per-murid = token statis tanpa waktu kedaluwarsa.
    # Ditutup: rate-limit per token+IP, dan maksimal 1 absen/hari per murid
    # (index unik idx_absen_1perday). Fotonya QR masih bisa di-titipin sampai
    # habis kuota harian â€” upgrade nyata: token sekali pakai / berjangka.
    if status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail="Status absensi tidak valid")

    check_absen_rate_limit(request, token)

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM murid WHERE token = ?", (token,))
    murid = cur.fetchone()
    if not murid:
        conn.close()
        raise HTTPException(status_code=404, detail="QR tidak valid")

    now    = datetime.now()
    jam    = now.strftime("%H:%M")
    tanggal = now.strftime("%Y-%m-%d")

    cur.execute("SELECT id FROM absensi WHERE murid_id = ? AND tanggal = ?", (murid["id"], tanggal))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="Absen hari ini sudah tercatat")

    cur.execute("""
        INSERT INTO absensi (murid_id, nama, kelas, unit, urutan, status, latitude, longitude, jam, tanggal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (murid["id"], murid["nama"], murid["kelas"], murid["unit"], murid["urutan"],
          status, latitude, longitude, jam, tanggal))
    conn.commit()
    absensi_id = cur.lastrowid
    conn.close()

    return {
        "ok": True,
        "id": absensi_id,
        "nama": murid["nama"],
        "kelas": murid["kelas"],
        "unit": murid["unit"],
        "status": status,
        "jam": jam,
        "tanggal": tanggal,
    }

# â”€â”€ Dashboard - Baca Absensi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/absensi")
def list_absensi(
    tanggal: Optional[str] = None,
    payload: dict = Depends(require_verified)
):
    unit = payload["unit"]
    if unit not in VALID_UNITS:
        raise HTTPException(status_code=403, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()

    if tanggal:
        if unit == "ALL":
            cur.execute("SELECT * FROM absensi WHERE tanggal = ? ORDER BY urutan, id", (tanggal,))
        else:
            cur.execute("SELECT * FROM absensi WHERE unit = ? AND tanggal = ? ORDER BY urutan, id",
                        (unit, tanggal))
    else:
        if unit == "ALL":
            cur.execute("SELECT * FROM absensi ORDER BY tanggal DESC, urutan, id LIMIT 200")
        else:
            cur.execute("SELECT * FROM absensi WHERE unit = ? ORDER BY tanggal DESC, urutan, id LIMIT 200", (unit,))

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# â”€â”€ Dashboard - Hapus Absensi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class DeleteIds(BaseModel):
    ids: list[int]

@app.delete("/api/absensi")
def delete_absensi(data: DeleteIds, payload: dict = Depends(require_verified)):
    if not data.ids:
        raise HTTPException(status_code=400, detail="Tidak ada ID yang dikirim")

    conn = get_conn()
    cur  = conn.cursor()

    placeholders = ",".join("?" * len(data.ids))
    cur.execute(
        f"DELETE FROM absensi WHERE id IN ({placeholders}) AND (unit = ? OR ? = 'ALL')",
        (*data.ids, payload["unit"], payload["unit"]),
    )
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return {"ok": True, "deleted": deleted}

# â”€â”€ Export Excel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/absensi/export")
def export_excel(
    tanggal: Optional[str] = None,
    payload: dict = Depends(require_verified)
):
    unit = payload["unit"]
    if unit not in VALID_UNITS:
        raise HTTPException(status_code=403, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()

    if tanggal:
        if unit == "ALL":
            cur.execute("SELECT * FROM absensi WHERE tanggal = ? ORDER BY urutan, id", (tanggal,))
        else:
            cur.execute("SELECT * FROM absensi WHERE unit = ? AND tanggal = ? ORDER BY urutan, id",
                        (unit, tanggal))
    else:
        if unit == "ALL":
            cur.execute("SELECT * FROM absensi ORDER BY tanggal DESC, urutan, id")
        else:
            cur.execute("SELECT * FROM absensi WHERE unit = ? ORDER BY tanggal DESC, urutan, id", (unit,))

    rows = cur.fetchall()
    conn.close()

    # Buat Excel
    wb = openpyxl.Workbook()
    ws = wb.active

    unit_label = unit if unit != "ALL" else "Semua Unit"
    ws.title   = f"Absensi {unit_label}"

    # Style
    header_fill   = PatternFill("solid", fgColor="1E3A5F")
    header_font   = Font(color="FFFFFF", bold=True, size=11)
    center_align  = Alignment(horizontal="center", vertical="center")
    border_side   = Side(style="thin", color="CCCCCC")
    cell_border   = Border(left=border_side, right=border_side,
                           top=border_side, bottom=border_side)

    # Judul
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value     = f"Rekap Absensi Murid {unit_label}"
    title_cell.font      = Font(bold=True, size=14, color="1E3A5F")
    title_cell.alignment = center_align
    if tanggal:
        ws.merge_cells("A2:I2")
        ws["A2"].value     = f"Tanggal: {tanggal}"
        ws["A2"].alignment = center_align
        ws["A2"].font      = Font(italic=True, color="666666")

    # Header tabel
    headers = ["No", "Tanggal", "Jam", "Nama Murid", "Kelas",
               "Unit", "Status", "Latitude", "Longitude"]
    start_row = 4
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=h)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = center_align
        cell.border    = cell_border

    # Data
    status_colors = {"Hadir": "D4EDDA", "Izin": "FFF3CD", "Sakit": "F8D7DA"}
    for i, row in enumerate(rows, 1):
        r = start_row + i
        values = [
            i, excel_safe(row["tanggal"]), excel_safe(row["jam"]),
            excel_safe(row["nama"]), excel_safe(row["kelas"]),
            excel_safe(row["unit"]), excel_safe(row["status"]),
            row["latitude"] or "-", row["longitude"] or "-"
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.alignment = center_align
            cell.border    = cell_border
            if col == 7:  # status
                color = status_colors.get(row["status"], "FFFFFF")
                cell.fill = PatternFill("solid", fgColor=color)

    # Lebar kolom
    col_widths = [5, 12, 8, 25, 22, 8, 10, 14, 14]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # Freeze header
    ws.freeze_panes = f"A{start_row + 1}"

    # Stream ke response
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"absensi_{unit_label}_{tanggal or 'semua'}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

# â”€â”€ Stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/stats")
def stats(tanggal: Optional[str] = None, payload: dict = Depends(require_verified)):
    unit = payload["unit"]
    if unit not in VALID_UNITS:
        raise HTTPException(status_code=403, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()

    params = []
    where  = []
    if unit != "ALL":
        where.append("unit = ?")
        params.append(unit)
    if tanggal:
        where.append("tanggal = ?")
        params.append(tanggal)
    where_sql = " AND ".join(where) if where else "1=1"

    cur.execute(f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='Hadir' THEN 1 ELSE 0 END) as hadir,
            SUM(CASE WHEN status='Izin'  THEN 1 ELSE 0 END) as izin,
            SUM(CASE WHEN status='Sakit' THEN 1 ELSE 0 END) as sakit
        FROM absensi WHERE {where_sql}
    """, params)
    row = dict(cur.fetchone())
    conn.close()
    return row

# â”€â”€ Rekap per Murid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.get("/api/rekap")
def rekap(
    start: Optional[str] = None,
    end: Optional[str] = None,
    payload: dict = Depends(require_verified),
):
    unit = payload["unit"]
    if unit not in VALID_UNITS:
        raise HTTPException(status_code=403, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()

    params = []
    where  = []
    if unit != "ALL":
        where.append("unit = ?")
        params.append(unit)
    if start:
        where.append("tanggal >= ?")
        params.append(start)
    if end:
        where.append("tanggal <= ?")
        params.append(end)
    where_sql = " AND ".join(where) if where else "1=1"

    cur.execute(f"""
        SELECT nama, kelas, unit, MIN(urutan) as urutan,
               COUNT(*) as total,
               SUM(CASE WHEN status='Hadir' THEN 1 ELSE 0 END) as hadir,
               SUM(CASE WHEN status='Izin'  THEN 1 ELSE 0 END) as izin,
               SUM(CASE WHEN status='Sakit' THEN 1 ELSE 0 END) as sakit
        FROM absensi WHERE {where_sql}
        GROUP BY nama, kelas, unit
        ORDER BY urutan, nama ASC
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/rekap/export")
def export_rekap_excel(
    start: Optional[str] = None,
    end: Optional[str] = None,
    payload: dict = Depends(require_verified),
):
    unit = payload["unit"]
    if unit not in VALID_UNITS:
        raise HTTPException(status_code=403, detail="Unit tidak valid")
    conn = get_conn()
    cur  = conn.cursor()

    params = []
    where  = []
    if unit != "ALL":
        where.append("unit = ?")
        params.append(unit)
    if start:
        where.append("tanggal >= ?")
        params.append(start)
    if end:
        where.append("tanggal <= ?")
        params.append(end)
    where_sql = " AND ".join(where) if where else "1=1"

    cur.execute(f"""
        SELECT nama, kelas, unit, MIN(urutan) as urutan,
               COUNT(*) as total,
               SUM(CASE WHEN status='Hadir' THEN 1 ELSE 0 END) as hadir,
               SUM(CASE WHEN status='Izin'  THEN 1 ELSE 0 END) as izin,
               SUM(CASE WHEN status='Sakit' THEN 1 ELSE 0 END) as sakit
        FROM absensi WHERE {where_sql}
        GROUP BY nama, kelas, unit
        ORDER BY urutan, nama ASC
    """, params)
    rows = cur.fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active

    unit_label = unit if unit != "ALL" else "Semua Unit"
    ws.title   = f"Rekap {unit_label}"

    header_fill  = PatternFill("solid", fgColor="1E3A5F")
    header_font  = Font(color="FFFFFF", bold=True, size=11)
    center_align = Alignment(horizontal="center", vertical="center")
    border_side  = Side(style="thin", color="CCCCCC")
    cell_border  = Border(left=border_side, right=border_side,
                          top=border_side, bottom=border_side)

    ws.merge_cells("A1:H1")
    title_cell = ws["A1"]
    title_cell.value     = f"Rekap Absensi Murid {unit_label}"
    title_cell.font      = Font(bold=True, size=14, color="1E3A5F")
    title_cell.alignment = center_align
    if start and end:
        ws.merge_cells("A2:H2")
        ws["A2"].value     = f"Periode: {start} s/d {end}"
        ws["A2"].alignment = center_align
        ws["A2"].font      = Font(italic=True, color="666666")

    headers = ["No", "Nama Murid", "Kelas", "Unit",
               "Hadir", "Izin", "Sakit", "Total"]
    start_row = 4
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=h)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = center_align
        cell.border    = cell_border

    status_colors = {"Hadir": "D4EDDA", "Izin": "FFF3CD", "Sakit": "F8D7DA"}
    for i, row in enumerate(rows, 1):
        r = start_row + i
        values = [i, excel_safe(row["nama"]), excel_safe(row["kelas"]),
                  excel_safe(row["unit"]),
                  row["hadir"], row["izin"], row["sakit"], row["total"]]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.alignment = center_align
            cell.border    = cell_border

    col_widths = [5, 25, 22, 8, 8, 8, 8, 8]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    ws.freeze_panes = f"A{start_row + 1}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"rekap_{unit_label}_{start or 'awal'}_{end or 'akhir'}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

# â”€â”€ Guru: materi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class MateriIn(BaseModel):
    judul: str
    isi: str

@app.get("/api/materi")
def list_materi(payload: dict = Depends(require_verified)):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT id, judul, isi, tanggal, created_by, created_at FROM materi ORDER BY tanggal DESC, id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/materi")
def create_materi(data: MateriIn, payload: dict = Depends(require_verified)):
    if not data.judul.strip() or not data.isi.strip():
        raise HTTPException(status_code=400, detail="Judul & isi materi wajib diisi")
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO materi (judul, isi, tanggal, created_by) VALUES (?, ?, ?, ?)",
        (data.judul.strip(), data.isi.strip(), datetime.now().strftime("%Y-%m-%d"), payload["sub"]))
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": mid}

@app.delete("/api/materi/{materi_id}")
def delete_materi(materi_id: int, payload: dict = Depends(require_verified)):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "DELETE FROM materi WHERE id = ? AND (created_by = ? OR ? = 'ALL')",
        (materi_id, payload["sub"], payload["unit"]))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
    return {"ok": True}

# â”€â”€ Guru: nilai â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class NilaiIn(BaseModel):
    murid_id: int
    mapel: str
    nilai: float
    tanggal: str = ""

@app.get("/api/nilai")
def list_nilai(murid_id: int = None, payload: dict = Depends(require_verified)):
    unit = payload["unit"]
    conn = get_conn()
    cur  = conn.cursor()
    if murid_id:
        cur.execute("""
            SELECT n.id, n.murid_id, n.mapel, n.nilai, n.tanggal
            FROM nilai n JOIN murid m ON m.id = n.murid_id
            WHERE n.murid_id = ? AND (m.unit = ? OR ? = 'ALL')
            ORDER BY n.tanggal DESC, n.id DESC
        """, (murid_id, unit, unit))
    else:
        cur.execute("""
            SELECT n.id, n.murid_id, n.mapel, n.nilai, n.tanggal
            FROM nilai n JOIN murid m ON m.id = n.murid_id
            WHERE m.unit = ? OR ? = 'ALL'
            ORDER BY n.tanggal DESC, n.id DESC
        """, (unit, unit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/nilai")
def create_nilai(data: NilaiIn, payload: dict = Depends(require_verified)):
    if not data.mapel.strip():
        raise HTTPException(status_code=400, detail="Mata pelajaran wajib diisi")
    if not (0 <= data.nilai <= 100):
        raise HTTPException(status_code=400, detail="Nilai harus 0-100")
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT id FROM murid WHERE id = ? AND (unit = ? OR ? = 'ALL')",
                (data.murid_id, payload["unit"], payload["unit"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Murid tidak ditemukan")
    tanggal = data.tanggal or datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO nilai (murid_id, mapel, nilai, tanggal) VALUES (?, ?, ?, ?)",
        (data.murid_id, data.mapel.strip(), data.nilai, tanggal))
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    return {"ok": True, "id": nid}

@app.get("/api/nilai/rata2")
def rata2_nilai(payload: dict = Depends(require_verified)):
    unit = payload["unit"]
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT m.id AS murid_id, m.nama, m.kelas,
               ROUND(AVG(n.nilai), 2) AS rata2, COUNT(n.id) AS jumlah
        FROM murid m LEFT JOIN nilai n ON n.murid_id = m.id
        WHERE m.unit = ? OR ? = 'ALL'
        GROUP BY m.id ORDER BY m.urutan, m.nama
    """, (unit, unit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.delete("/api/nilai/{nilai_id}")
def delete_nilai(nilai_id: int, payload: dict = Depends(require_verified)):
    unit = payload["unit"]
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        DELETE FROM nilai WHERE id = ? AND murid_id IN (
            SELECT id FROM murid WHERE unit = ? OR ? = 'ALL'
        )
    """, (nilai_id, unit, unit))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Nilai tidak ditemukan")
    return {"ok": True}

# â”€â”€ Session store untuk challenge login â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_temp_sessions = {}
_temp_session_max = 100
_temp_session_ttl = 300  # 5 menit

# â”€â”€ Auth Seed & Recovery Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.post("/api/admin/setup-seed-and-key")
def setup_seed_and_key_endpoint(payload: dict = Depends(verify_token)):
    """
    Setup seed phrase DAN recovery key sekaligus.
    Hanya admin yang sudah login yang bisa akses ini.
    """
    seed = generate_seed_phrase()
    seed_str = " ".join(seed)
    mapping = build_mapping(seed)
    recovery_key=generate_recovery_key(64)
    
    setup_seed_and_key(
        username=payload["sub"],
        seed=seed,
        recovery_key=recovery_key,
        mapping=mapping
    )
    
    return {
        "message": "Seed phrase dan Recovery Key berhasil dibuat!",
        "seed_phrase": seed_str,
        "mapping": [[m[0], m[1], m[2]] for m in mapping],
        "recovery_key": recovery_key,
        "warning": "âš ï¸ SIMPAN RECOVERY KEY DI FLASHDISK! Key ini TIDAK akan expired."
    }

@app.get("/api/admin/seed/quiz")
def seed_quiz(payload: dict = Depends(verify_token)):
    """Ambil 12 kata seed admin + 10 kata pengganggu, diacak. Untuk verifikasi mana
    yang termasuk 12 kata miliknya."""
    admin_data = get_admin_seed_data(payload["sub"])
    if not admin_data or not admin_data["mapping"]:
        raise HTTPException(400, "Belum ada seed. Generate dulu.")
    seed_words = [m[1] for m in admin_data["mapping"]]
    decoys = [w for w in WORDLIST if w not in seed_words]
    import random as _random
    _random.shuffle(decoys)
    candidates = seed_words + decoys[:10]
    _random.shuffle(candidates)
    return {"words": candidates, "total": len(seed_words)}

@app.post("/api/admin/seed/verify-words")
def seed_verify_words(data: dict, payload: dict = Depends(verify_token)):
    """Cek jawaban verifikasi: kata yang dipilih harus cocok persis (multiset) dengan
    kata-kata seed admin (mendukung kata duplikat). Sekali kata salah => ditolak."""
    from collections import Counter
    admin_data = get_admin_seed_data(payload["sub"])
    if not admin_data or not admin_data["mapping"]:
        raise HTTPException(400, "Belum ada seed. Generate dulu.")
    seed_words = Counter(m[1].lower() for m in admin_data["mapping"])
    picked = Counter(str(w).strip().lower() for w in data.get("words", []))
    if picked != seed_words:
        # jangan bocorkan jumlah yang salah, cukup tolak
        raise HTTPException(400, "Jawaban belum tepat, coba lagi.")
    return {"ok": True, "message": "Verifikasi berhasil! Seed tersimpan aman."}

@app.get("/api/admin/seed/status")
def seed_status(payload: dict = Depends(verify_token)):
    """Status seed admin: sudah ada belum / sudah diverifikasi belum."""
    import database
    conn = database.get_conn()
    cur = conn.cursor()
    cur.execute("SELECT must_change_password FROM admin WHERE username = ?", (payload["sub"],))
    row = cur.fetchone()
    conn.close()
    admin_data = get_admin_seed_data(payload["sub"])
    if not admin_data:
        raise HTTPException(400, "Data admin tidak ditemukan.")
    has_seed = bool(admin_data["seed_hash"] and admin_data["mapping"])
    seed_phrase = None
    mapping = None
    if has_seed:
        seed_phrase = " ".join(m[1] for m in admin_data["mapping"])
        mapping = [list(m) for m in admin_data["mapping"]]
    return {
        "has_seed": has_seed,
        "seed_verified": bool(admin_data["seed_verified"]),
        "must_change_password": bool(row["must_change_password"]) if row else False,
        "seed_phrase": seed_phrase,
        "mapping": mapping,
    }

@app.post("/api/admin/seed/challenge3")
def seed_challenge3(payload: dict = Depends(verify_token)):
    """Quiz 3 kata ala wallet kripto (BIP-39): ambil 3 posisi acak dari seed,
    masing-masing dibawa daftar kata campur (benar + pengecoh)."""
    import random as _random
    import uuid
    import time as _time
    now = _time.time()
    stale = [k for k, v in _temp_sessions.items() if now - v.get("ts", 0) > _temp_session_ttl]
    for k in stale:
        del _temp_sessions[k]
    if len(_temp_sessions) >= _temp_session_max:
        raise HTTPException(429, "Terlalu banyak sesi aktif. Coba lagi nanti.")
    admin_data = get_admin_seed_data(payload["sub"])
    if not admin_data or not admin_data["mapping"]:
        raise HTTPException(400, "Belum ada seed. Generate dulu.")
    seed_words = [m[1] for m in admin_data["mapping"]]
    positions = _random.sample(range(12), 3)
    questions = []
    for pos in positions:
        correct = seed_words[pos]
        decoys = _random.sample([w for w in WORDLIST if w != correct], 5)
        options = [correct] + decoys
        _random.shuffle(options)
        questions.append({"position": pos + 1, "options": options})
    challenge_id = str(uuid.uuid4())[:16]
    _temp_sessions[challenge_id] = {
        "username": payload["sub"],
        "answers": {pos + 1: seed_words[pos] for pos in positions},
        "attempts": 0,
        "ts": now,
    }
    return {"challenge_id": challenge_id, "questions": questions}

@app.post("/api/admin/seed/verify3")
def seed_verify3(data: dict, payload: dict = Depends(verify_token)):
    """Cek jawaban quiz 3 kata. Cukup 3 jawaban benar â†’ seed resmi terverifikasi."""
    import time
    challenge_id = data.get("challenge_id", "")
    answers = data.get("answers") or {}
    session = _temp_sessions.get(challenge_id)
    if not session:
        raise HTTPException(400, "Challenge kadaluarsa. Coba lagi.")
    if session["username"] != payload["sub"]:
        raise HTTPException(401, "Challenge milik user lain.")
    if session["attempts"] >= 3:
        del _temp_sessions[challenge_id]
        raise HTTPException(429, "Terlalu banyak salah.")
    correct = all(str(answers.get(str(k), "")).strip().lower() == str(v).lower()
                 for k, v in session["answers"].items())
    if not correct:
        session["attempts"] += 1
        raise HTTPException(401, "Jawaban belum tepat.")
    del _temp_sessions[challenge_id]
    mark_seed_verified(payload["sub"])
    return {"ok": True, "message": "Verifikasi berhasil! Seed terverifikasi resmi."}

@app.post("/api/login/challenge")
def login_challenge(form: OAuth2PasswordRequestForm = Depends()):
    """Step 1: Generate challenge berdasarkan username."""
    import uuid
    username = form.username
    admin_data = get_admin_seed_data(username)
    
    if not admin_data or not admin_data["mapping"]:
        raise HTTPException(400, "User belum setup seed phrase.")
    
    challenge = generate_challenge(admin_data["mapping"])
    session_token=str(uuid.uuid4())[:16]
    
    _temp_sessions[session_token] = {
        "username": username,
        "challenge_answer": challenge["answer"],
        "mapping_index": challenge["seed_index"],
        "attempts": 0,
    }
    
    return {
        "question": challenge["question"],
        "session_token": session_token,
        "hint": "Jawablah sesuai yang kamu hafal."
    }

@app.post("/api/login/verify-challenge")
def verify_challenge_endpoint(data: dict):
    """Step 2: Verifikasi jawaban challenge."""
    import time
    session_token = data.get("session_token", "")
    answer = data.get("answer", "").strip().lower()
    session = _temp_sessions.get(session_token)
    
    if not session:
        raise HTTPException(400, "Session expired. Login lagi.")
    if session["attempts"] >= 3:
        del _temp_sessions[session_token]
        raise HTTPException(429, "Terlalu banyak salah.")
    
    if answer == session["challenge_answer"]:
        return {"success": True}
    else:
        session["attempts"] += 1
        raise HTTPException(401, "Jawaban salah.")

@app.post("/api/login/verify-seed")
def verify_seed_login(data: dict):
    """Step 3: Verifikasi seed phrase."""
    session_token = data.get("session_token", "")
    seed_phrase = data.get("seed_phrase", "").strip()
    session = _temp_sessions.get(session_token)
    
    if not session:
        raise HTTPException(400, "Session tidak valid.")
    
    admin_data = get_admin_seed_data(session["username"])
    if not admin_data or not admin_data["seed_hash"]:
        raise HTTPException(404, "Data seed tidak ditemukan.")
    
    if verify_seed(admin_data["seed_hash"], seed_phrase):
        token = create_token({"sub": session["username"], "unit": admin_data["unit"]})
        del _temp_sessions[session_token]
        return {"access_token": token, "token_type": "bearer", "unit": admin_data["unit"]}
    else:
        raise HTTPException(401, "Seed phrase salah.")

@app.post("/api/login/recovery")
def login_recovery(data: dict):
    """
    Login fallback pakai recovery key.
    RECOVERY KEY TIDAK EXPIRED - bisa dipakai kapan saja.
    """
    recovery_key_input = data.get("recovery_key", "").strip()
    if not recovery_key_input or len(recovery_key_input) < 32:
        raise HTTPException(400, "Recovery key tidak valid.")
    
    all_admins = get_all_admin_seed_data()
    for admin in all_admins:
        if admin["recovery_key_hash"] and verify_recovery_key(
            admin["recovery_key_hash"], recovery_key_input
        ):
            token = create_token({"sub": admin["username"], "unit": admin["unit"]})
            return {
                "access_token": token, "token_type": "bearer",
                "unit": admin["unit"], "username": admin["username"],
                "message": "Login berhasil pakai recovery key."
            }
    raise HTTPException(401, "Recovery key tidak ditemukan.")

# â”€â”€ Portfolio galeri (landing page) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from fastapi import UploadFile, File

PORTFOLIO_DIR = os.path.join(os.path.dirname(__file__), "dashboard", "static", "img", "portfolio")
os.makedirs(PORTFOLIO_DIR, exist_ok=True)
PORTFOLIO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm"}

@app.get("/api/portfolio/list")
def portfolio_list():
    try:
        return sorted(
            f for f in os.listdir(PORTFOLIO_DIR)
            if os.path.splitext(f)[1].lower() in PORTFOLIO_EXT
        )
    except FileNotFoundError:
        return []

@app.post("/api/portfolio/upload")
async def portfolio_upload(file: UploadFile = File(...), payload: dict = Depends(require_verified)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in PORTFOLIO_EXT:
        raise HTTPException(status_code=400, detail="Format harus jpg/png/gif/webp/mp4/webm")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 15MB")
    name = f"{int(time())}{ext}"
    with open(os.path.join(PORTFOLIO_DIR, name), "wb") as f:
        f.write(data)
    return {"ok": True, "name": name}

@app.delete("/api/portfolio/{name}")
def portfolio_delete(name: str, payload: dict = Depends(require_verified)):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Nama file tidak valid")
    path = os.path.join(PORTFOLIO_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    os.remove(path)
    return {"ok": True}















