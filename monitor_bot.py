"""
Bot Monitor Keamanan — Yamasy SIEM Mini
Fitur:
- Auto alert server mati/hidup (multi-endpoint)
- Auto alert lonjakan traffic anomali
- Auto alert brute force login (percobaan gagal & diblokir)
- Auto laporan harian
- Menu grafik traffic on-demand
- Menu log request terakhir
- Menu status server & log anomali
"""

import os
import sys
import json
import time
import asyncio
import hashlib
import logging
import sqlite3
import httpx
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env
load_env()

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")
CHAT_ID       = os.getenv("CHAT_ID", "")
BACKEND_URL   = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_API_KEY   = os.getenv("BOT_API_KEY", "")
PROJECT_DIR   = os.getenv("PROJECT_DIR", r"C:\absensi-guru")

if not CHAT_ID:
    raise RuntimeError("CHAT_ID belum di-set di .env")
CHAT_ID = int(CHAT_ID)

if not MONITOR_TOKEN:
    raise RuntimeError("MONITOR_TOKEN belum di-set di .env")

API_HEADERS   = {"X-API-Key": BOT_API_KEY}

# Interval cek (detik)
CHECK_INTERVAL     = 30   # cek server tiap 30 detik
TRAFFIC_INTERVAL   = 60   # analisa traffic tiap 1 menit
FILE_WATCH_INTERVAL= 60   # cek perubahan file tiap 1 menit

# Threshold anomali
TRAFFIC_SPIKE_MULT = 3    # dianggap lonjakan kalau 3x lipat rata-rata
FAILED_LOGIN_ALERT = 5    # alert kalau ≥ 5 percobaan login gagal/menit

# Laporan harian otomatis (jam lokal, 24h)
DAILY_REPORT_HOUR  = 21   # kirim laporan tiap 21:00

# Endpoint yang dipantau statusnya
OK_STATUSES = (200, 401, 403, 422)  # 401/403 = auth aktif (server normal)
ENDPOINTS = [
    ("Dashboard API",  f"{BACKEND_URL}/api/me",                  {"Authorization": "Bearer dummy"}),
    ("Stats API",      f"{BACKEND_URL}/api/stats",               {"Authorization": "Bearer dummy"}),
    ("Rekap API",      f"{BACKEND_URL}/api/rekap",               {"Authorization": "Bearer dummy"}),
    ("Monitor API",    f"{BACKEND_URL}/api/monitor/traffic",     API_HEADERS),
]

# ── State ─────────────────────────────────────────────────────────────────────
server_was_up    = True
file_hashes      = {}
traffic_log      = []     # list of {"time": datetime, "count": int}
error_log        = []     # list of {"time": datetime, "count": int}
request_log      = []     # list of {"time", "method", "path", "status", "ip"}
anomaly_log      = []     # list of {"time", "type", "detail"}
login_failed_last = 0     # counter login gagal terakhir (dari backend)
login_blocked_last = 0    # counter login diblokir terakhir
error_last        = 0     # counter error terakhir

ANOMALY_LOG_MAX = 200

def log_anomali(typ: str, detail: str):
    anomaly_log.append({"time": datetime.now(), "type": typ, "detail": detail})
    if len(anomaly_log) > ANOMALY_LOG_MAX:
        anomaly_log.pop(0)

# ── File Watcher ──────────────────────────────────────────────────────────────
WATCH_EXTENSIONS = {".py", ".js", ".html", ".css"}
IGNORE_DIRS      = {"__pycache__", ".git", "uploads", "node_modules"}

def hash_file(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""

def scan_files() -> dict:
    hashes = {}
    for ext in WATCH_EXTENSIONS:
        for p in Path(PROJECT_DIR).rglob(f"*{ext}"):
            if not any(ig in p.parts for ig in IGNORE_DIRS):
                hashes[str(p)] = hash_file(str(p))
    return hashes

def init_file_hashes():
    global file_hashes
    file_hashes = scan_files()
    logger.info(f"[FileWatch] Memantau {len(file_hashes)} file")

# ── Backup Excel ───────────────────────────────────────────────────────────────
def create_backup_bytes():
    """Export semua tabel DB ke workbook Excel (BytesIO + nama file)."""
    db = Path(__file__).resolve().parent / "backend" / "absensi.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    logger.info(f"[Backup] DB={db} | tabel={tables}")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for tbl in tables:
        rows = cur.execute(f"SELECT * FROM {tbl}").fetchall()
        if not rows:
            continue  # ponytail: tabel kosong gak ditampilkan, biar gak tampak 'kosong'
        ws = wb.create_sheet(title=tbl[:31])
        ws.append(list(rows[0].keys()))
        for r in rows:
            ws.append(list(r))
    conn.close()
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

# ── Grafik ────────────────────────────────────────────────────────────────────
def generate_traffic_chart(hours: int = 24) -> BytesIO:
    now    = datetime.now()
    since  = now - timedelta(hours=hours)

    # Filter data sesuai range
    data = [t for t in traffic_log if t["time"] >= since]

    # Buat bucket per jam
    buckets = defaultdict(int)
    for entry in data:
        bucket = entry["time"].replace(minute=0, second=0, microsecond=0)
        buckets[bucket] += entry["count"]

    # Isi jam yang kosong
    times  = []
    counts = []
    cur = since.replace(minute=0, second=0, microsecond=0)
    while cur <= now:
        times.append(cur)
        counts.append(buckets.get(cur, 0))
        cur += timedelta(hours=1)

    # Plot
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor('#1E293B')
    ax.set_facecolor('#0F172A')

    ax.plot(times, counts, color='#3B82F6', linewidth=2, marker='o', markersize=4)
    ax.fill_between(times, counts, alpha=0.2, color='#3B82F6')

    # Tandai anomali
    avg = sum(counts) / len(counts) if counts else 0
    for i, (t, c) in enumerate(zip(times, counts)):
        if avg > 0 and c >= avg * TRAFFIC_SPIKE_MULT:
            ax.axvline(x=t, color='#EF4444', alpha=0.5, linestyle='--')
            ax.annotate('⚠️ Spike', xy=(t, c), color='#EF4444', fontsize=8)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, hours//12)))
    plt.xticks(rotation=45, color='#94A3B8', fontsize=8)
    plt.yticks(color='#94A3B8', fontsize=8)

    ax.set_title(f'Traffic {hours} Jam Terakhir', color='#F1F5F9', fontsize=13, pad=12)
    ax.set_xlabel('Waktu', color='#94A3B8', fontsize=10)
    ax.set_ylabel('Jumlah Request', color='#94A3B8', fontsize=10)
    ax.grid(True, color='#334155', alpha=0.5, linestyle='--')

    for spine in ax.spines.values():
        spine.set_color('#334155')

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return buf

# ── Monitor Tasks ─────────────────────────────────────────────────────────────
async def task_cek_server(app: Application):
    global server_was_up
    while True:
        results = {}
        try:
            async with httpx.AsyncClient() as client:
                for name, url, headers in ENDPOINTS:
                    try:
                        r = await client.get(url, timeout=10, headers=headers)
                        results[name] = r.status_code in OK_STATUSES
                    except Exception:
                        results[name] = False
                is_up = all(results.values())
        except Exception:
            is_up = False

        if not is_up and server_was_up:
            server_was_up = False
            ts = datetime.now().strftime("%H:%M:%S")
            detail_lines = ""
            for name, ok in results.items():
                detail_lines += f"{'✅' if ok else '❌'} `{name}`\n"
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"🔴 *SERVER MATI!*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"⏰ Waktu: `{ts}`\n"
                    f"🌐 URL: `{BACKEND_URL}`\n\n"
                    f"{detail_lines}"
                    f"\nBackend tidak merespons. Segera periksa!"
                ),
                parse_mode="Markdown"
            )
            log_anomali("SERVER_DOWN", f"Tidak merespons sejak {ts}")

        elif is_up and not server_was_up:
            server_was_up = True
            ts = datetime.now().strftime("%H:%M:%S")
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"🟢 *SERVER KEMBALI ONLINE!*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"⏰ Waktu: `{ts}`\n"
                    f"✅ Semua endpoint merespons normal kembali."
                ),
                parse_mode="Markdown"
            )

        await asyncio.sleep(CHECK_INTERVAL)

async def task_monitor_traffic(app: Application):
    """Ambil log dari FastAPI dan analisa anomali."""
    global request_log, traffic_log, error_log, error_last
    global login_failed_last, login_blocked_last
    last_count = 0

    while True:
        await asyncio.sleep(TRAFFIC_INTERVAL)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{BACKEND_URL}/api/monitor/traffic",
                                     headers=API_HEADERS, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    current_count = data.get("total_requests", 0)
                    new_requests  = current_count - last_count

                    # Simpan ke traffic log
                    traffic_log.append({"time": datetime.now(), "count": new_requests})
                    if len(traffic_log) > 1440:  # simpan max 24 jam
                        traffic_log.pop(0)

                    # Tracking error
                    current_error = data.get("error_count", 0)
                    new_errors    = max(0, current_error - error_last)
                    error_log.append({"time": datetime.now(), "count": new_errors})
                    if len(error_log) > 1440:
                        error_log.pop(0)
                    error_last = current_error

                    # ── Alert brute force login ──
                    login_blocked = data.get("login_blocked", 0)
                    login_failed  = data.get("login_failed", 0)
                    new_blocks = login_blocked - login_blocked_last
                    new_failed = login_failed - login_failed_last

                    if new_blocks > 0:
                        ts = datetime.now().strftime("%H:%M:%S")
                        log_anomali("LOGIN_BLOCKED", f"{new_blocks} diblokir rate limit")
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=(
                                f"🔒 *BRUTE FORCE TERDETEKSI!*\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"⏰ Waktu: `{ts}`\n"
                                f"🚫 Percobaan login diblokir rate limit: *{new_blocks}*\n\n"
                                f"Ada yang mencoba paksa login! Periksa IP mencurigakan."
                            ),
                            parse_mode="Markdown"
                        )

                    if new_failed >= FAILED_LOGIN_ALERT:
                        ts = datetime.now().strftime("%H:%M:%S")
                        log_anomali("LOGIN_FAILED", f"{new_failed} gagal/menit")
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=(
                                f"⚠️ *BANYAK PERCOBAAN LOGIN GAGAL!*\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"⏰ Waktu: `{ts}`\n"
                                f"❌ Login gagal dalam 1 menit: *{new_failed}*\n\n"
                                f"Kemungkinan serangan brute force atau typo password."
                            ),
                            parse_mode="Markdown"
                        )

                    login_blocked_last = login_blocked
                    login_failed_last  = login_failed

                    # Analisa anomali lonjakan
                    if len(traffic_log) >= 5:
                        recent  = [t["count"] for t in traffic_log[-5:]]
                        avg     = sum(recent[:-1]) / len(recent[:-1]) if recent[:-1] else 0
                        current = recent[-1]

                        if avg > 0 and current >= avg * TRAFFIC_SPIKE_MULT:
                            ts = datetime.now().strftime("%H:%M:%S")
                            log_anomali("TRAFFIC_SPIKE", f"{current} req/menit (rata-rata: {avg:.0f})")

                            await app.bot.send_message(
                                chat_id=CHAT_ID,
                                text=(
                                    f"⚠️ *LONJAKAN TRAFFIC ANOMALI!*\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"⏰ Waktu: `{ts}`\n"
                                    f"📈 Request: *{current}* req/menit\n"
                                    f"📊 Rata-rata normal: *{avg:.0f}* req/menit\n"
                                    f"🔺 Lonjakan: *{current/avg:.1f}x* lipat\n\n"
                                    f"Periksa apakah ada aktivitas mencurigakan!"
                                ),
                                parse_mode="Markdown"
                            )

                    # Anomali error rate tinggi
                    error_count = data.get("error_count", 0)
                    total       = data.get("total_requests", 1)
                    error_rate  = (error_count / total * 100) if total > 0 else 0
                    if error_rate > 80:
                        ts = datetime.now().strftime("%H:%M:%S")
                        await app.bot.send_message(
                            chat_id=CHAT_ID,
                            text=(
                                f"🚨 *ERROR RATE TINGGI!*\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"⏰ Waktu: `{ts}`\n"
                                f"❌ Error rate: *{error_rate:.1f}%*\n"
                                f"📊 Total error: *{error_count}* dari *{total}* request\n\n"
                                f"Kemungkinan ada masalah di sistem!"
                            ),
                            parse_mode="Markdown"
                        )

                    last_count = current_count
        except Exception as e:
            logger.error(f"Monitor traffic error: {e}")

async def task_file_watcher(app: Application):
    global file_hashes
    while True:
        await asyncio.sleep(FILE_WATCH_INTERVAL)
        try:
            current = scan_files()
            changed = []
            added   = []
            deleted = []

            for path, h in current.items():
                if path not in file_hashes:
                    added.append(path)
                elif file_hashes[path] != h:
                    changed.append(path)

            for path in file_hashes:
                if path not in current:
                    deleted.append(path)

            if changed or added or deleted:
                ts   = datetime.now().strftime("%H:%M:%S")
                msg  = f"📝 *PERUBAHAN FILE TERDETEKSI!*\n━━━━━━━━━━━━━━━\n⏰ Waktu: `{ts}`\n\n"

                if changed:
                    msg += "✏️ *Diubah:*\n"
                    for p in changed[:5]:
                        msg += f"  • `{Path(p).name}`\n"

                if added:
                    msg += "\n➕ *File Baru:*\n"
                    for p in added[:5]:
                        msg += f"  • `{Path(p).name}`\n"

                if deleted:
                    msg += "\n🗑 *Dihapus:*\n"
                    for p in deleted[:5]:
                        msg += f"  • `{Path(p).name}`\n"

                if len(changed) + len(added) + len(deleted) > 5:
                    msg += f"\n_...dan {len(changed)+len(added)+len(deleted)-5} file lainnya_"

                await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                log_anomali("FILE_CHANGE", f"Berubah: {len(changed)}, Baru: {len(added)}, Hapus: {len(deleted)}")

                file_hashes = current
        except Exception as e:
            logger.error(f"FileWatcher error: {e}")

# ── Laporan Harian ────────────────────────────────────────────────────────────
async def task_laporan_harian(app: Application):
    """Kirim ringkasan harian otomatis setiap DAILY_REPORT_HOUR."""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=DAILY_REPORT_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())

        try:
            today = datetime.now().date()
            total_req = sum(t["count"] for t in traffic_log if t["time"].date() == today)
            total_err = sum(t["count"] for t in error_log if t["time"].date() == today)
            anomali   = [a for a in anomaly_log if a["time"].date() == today]

            jenis = {}
            for a in anomali:
                jenis[a["type"]] = jenis.get(a["type"], 0) + 1
            jenis_txt = "  • ".join(f"{k}: {v}" for k, v in jenis.items()) if jenis else "Tidak ada"

            status = "🟢 Online" if server_was_up else "🔴 Offline"

            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=(
                    f"📊 *LAPORAN HARIAN*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🗓 Tanggal: `{today.strftime('%d-%m-%Y')}`\n"
                    f"🕐 Dibuat: `{datetime.now().strftime('%H:%M:%S')}`\n\n"
                    f"🌐 Status server: {status}\n"
                    f"📈 Total request: *{total_req}*\n"
                    f"❌ Total error: *{total_err}*\n"
                    f"🚨 Anomali hari ini:\n"
                    f"  {jenis_txt}\n\n"
                    f"ℹ️ _Rekap dihitung dari data yang terekam bot._"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Laporan harian error: {e}")

# ── Bot Handlers ──────────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    return update.effective_user.id == CHAT_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    keyboard = [
        [
            InlineKeyboardButton("📊 Grafik Traffic",   callback_data="grafik_24"),
            InlineKeyboardButton("📈 Grafik 6 Jam",     callback_data="grafik_6"),
        ],
        [
            InlineKeyboardButton("📋 Log Anomali",      callback_data="log_anomali"),
            InlineKeyboardButton("🔍 Status Server",    callback_data="status_server"),
        ],
        [
            InlineKeyboardButton("🕐 Log Request",      callback_data="last_requests"),
            InlineKeyboardButton("📁 File Berubah",     callback_data="file_changes"),
        ],
        [
            InlineKeyboardButton("💾 Backup Excel",     callback_data="backup"),
        ],
    ]
    await update.message.reply_text(
        "🛡️ *Yamasy Security Monitor*\n"
        "━━━━━━━━━━━━━━━\n"
        "Sistem monitoring aktif. Pilih menu:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != CHAT_ID:
        return

    data = query.data

    if data.startswith("grafik_"):
        hours = int(data.split("_")[1])
        await query.message.reply_text("⏳ Membuat grafik...")
        try:
            buf = generate_traffic_chart(hours)
            total = sum(t["count"] for t in traffic_log if t["time"] >= datetime.now() - timedelta(hours=hours))
            await query.message.reply_photo(
                photo=buf,
                caption=(
                    f"📊 *Traffic {hours} Jam Terakhir*\n"
                    f"Total request: *{total}*\n"
                    f"Dibuat: `{datetime.now().strftime('%H:%M:%S')}`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Gagal buat grafik: {e}")

    elif data == "status_server":
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{BACKEND_URL}/api/me", timeout=5,
                                     headers={"Authorization": "Bearer dummy"})
                is_up = r.status_code in (200, 401, 422)
        except Exception as e:
            logger.error(f"Cek status server error: {e}")
            is_up = False

        status = "🟢 ONLINE" if is_up else "🔴 OFFLINE"
        await query.message.reply_text(
            f"🔍 *Status Server*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Status: *{status}*\n"
            f"URL: `{BACKEND_URL}`\n"
            f"Waktu cek: `{datetime.now().strftime('%H:%M:%S')}`",
            parse_mode="Markdown"
        )

    elif data == "last_requests":
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{BACKEND_URL}/api/monitor/requests?limit=10",
                                     headers=API_HEADERS, timeout=10)
            if r.status_code == 200:
                reqs = r.json()
                if not reqs:
                    await query.message.reply_text("📭 Belum ada request tercatat.")
                    return
                msg = "🕐 *Request Terakhir*\n━━━━━━━━━━━━━━━\n"
                for req in reqs[:10]:
                    st = req["status"]
                    emoji = "✅" if st < 400 else ("⚠️" if st < 500 else "❌")
                    msg += (
                        f"{emoji} `{req['time']}` {req['method']} "
                        f"`{req['path']}` → *{st}*\n"
                    )
                await query.message.reply_text(msg, parse_mode="Markdown")
            else:
                await query.message.reply_text(f"❌ Gagal ambil log (HTTP {r.status_code}).")
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")

    elif data == "log_anomali":
        if not anomaly_log:
            await query.message.reply_text("✅ Tidak ada anomali tercatat.")
            return

        msg = "🚨 *Log Anomali Terakhir*\n━━━━━━━━━━━━━━━\n"
        for a in anomaly_log[-10:][::-1]:
            emoji = {"SERVER_DOWN": "🔴", "TRAFFIC_SPIKE": "⚠️", "FILE_CHANGE": "📝", "HIGH_ERROR": "❌", "LOGIN_BLOCKED": "🔒", "LOGIN_FAILED": "⚠️"}.get(a["type"], "⚠️")
            msg += f"{emoji} `{a['time'].strftime('%H:%M')}` — *{a['type']}*\n_{a['detail']}_\n\n"
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "file_changes":
        current = scan_files()
        changed = [p for p, h in current.items() if p in file_hashes and file_hashes[p] != h]
        if not changed:
            await query.message.reply_text("✅ Tidak ada perubahan file terdeteksi.")
        else:
            msg = f"📁 *File yang Berubah*\n━━━━━━━━━━━━━━━\n"
            for p in changed[:15]:
                msg += f"• `{Path(p).name}`\n"
            await query.message.reply_text(msg, parse_mode="Markdown")

    elif data == "backup":
        await query.message.reply_text("⏳ Membuat backup Excel...")
        try:
            buf, fname = create_backup_bytes()
            payload = buf.getvalue()
            logger.info(f"[Backup] {fname} = {len(payload)} bytes")
            await query.message.reply_document(
                document=payload,
                filename=fname,
                caption="💾 *Backup Data Lengkap*\n"
                        "Semua tabel database (admin, guru, absensi).",
            )
        except Exception as e:
            logger.error(f"[Backup] gagal: {e}")
            await query.message.reply_text(f"❌ Gagal backup: {e}")

async def post_init(app: Application):
    """Jalankan semua background task setelah bot siap."""
    init_file_hashes()
    asyncio.create_task(task_cek_server(app))
    asyncio.create_task(task_monitor_traffic(app))
    asyncio.create_task(task_file_watcher(app))
    asyncio.create_task(task_laporan_harian(app))

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "🛡️ *Yamasy Monitor Aktif!*\n"
            "━━━━━━━━━━━━━━━\n"
            f"✅ Memantau server: `{BACKEND_URL}`\n"
            f"📁 Memantau {len(file_hashes)} file kode\n"
            f"⏰ Cek server tiap {CHECK_INTERVAL} detik\n\n"
            "Ketik /start untuk menu."
        ),
        parse_mode="Markdown"
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = (
        Application.builder()
        .token(MONITOR_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🛡️ Yamasy Monitor berjalan...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()