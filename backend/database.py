import secrets
import sqlite3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
from env_loader import load_env
load_env()

# Rail mount a persistent volume here; default keeps local dev working.
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "absensi.db"))


def new_token() -> str:
    return secrets.token_urlsafe(16)


def _schema_sql(cur, table):
    row = cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return (row[0] if row else "") or ""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Migrasi dari schema lama (guru): ubah tabel jadi murid.
    if _schema_sql(cur, "guru"):
        cols = [r[1] for r in cur.execute("PRAGMA table_info(guru)").fetchall()]
        cur.execute("ALTER TABLE guru RENAME TO murid_old")
        cur.execute("""
            CREATE TABLE murid (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                nama TEXT NOT NULL,
                kelas TEXT NOT NULL,
                unit TEXT NOT NULL CHECK(unit IN ('MI', 'MTs', 'RA')),
                urutan INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        sel_kelas = "mapel" if "mapel" in cols else "''"
        cur.execute(f"""
            INSERT INTO murid (id, token, nama, kelas, unit, urutan, created_at)
            SELECT id, COALESCE(token, 'legacy-' || id), nama, {sel_kelas}, unit, id, created_at
            FROM murid_old
        """)
        cur.execute("DROP TABLE murid_old")
        if _schema_sql(cur, "absensi") and "guru_id" in [r[1] for r in cur.execute("PRAGMA table_info(absensi)").fetchall()]:
            cur.execute("ALTER TABLE absensi RENAME TO absensi_old")
            cur.execute("""
                CREATE TABLE absensi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    murid_id INTEGER NOT NULL,
                    nama TEXT NOT NULL,
                    kelas TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    urutan INTEGER,
                    status TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    jam TEXT NOT NULL,
                    tanggal TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (murid_id) REFERENCES murid(id)
                )
            """)
            acols = [r[1] for r in cur.execute("PRAGMA table_info(absensi_old)").fetchall()]
            a_kelas = "mapel" if "mapel" in acols else "''"
            a_status = "status" if "status" in acols else "'Hadir'"
            cur.execute(f"""
                INSERT INTO absensi (id, murid_id, nama, kelas, unit, urutan, status,
                                     latitude, longitude, jam, tanggal, created_at)
                SELECT id, guru_id, nama, {a_kelas}, unit, guru_id, {a_status},
                       latitude, longitude, jam, tanggal, created_at
                FROM absensi_old
            """)
            cur.execute("DROP TABLE absensi_old")
        conn.commit()

    # Tabel murid (didaftarkan oleh admin)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS murid (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            unit TEXT NOT NULL CHECK(unit IN ('MI', 'MTs', 'RA')),
            urutan INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Tabel absensi
    cur.execute("""
        CREATE TABLE IF NOT EXISTS absensi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            murid_id INTEGER NOT NULL,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            unit TEXT NOT NULL,
            urutan INTEGER,
            status TEXT NOT NULL CHECK(status IN ('Hadir', 'Izin', 'Sakit')),
            latitude REAL,
            longitude REAL,
            jam TEXT NOT NULL,
            tanggal TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (murid_id) REFERENCES murid(id)
        )
    """)

    # Hapus duplikat (sisakan yang paling awal), lalu kunci 1 absen/hari per murid.
    cur.execute("""
        DELETE FROM absensi WHERE id NOT IN (
            SELECT MIN(id) FROM absensi GROUP BY murid_id, tanggal
        )
    """)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_absen_1perday ON absensi(murid_id, tanggal)"
    )

    # Tabel admin
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            unit TEXT NOT NULL CHECK(unit IN ('MI', 'MTs', 'RA', 'ALL')),
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")

def seed_admin():
    """Buat/update akun admin dari .env (source of truth)."""
    from passlib.hash import bcrypt

    admins = [
        ("admin_mi",  os.getenv("ADMIN_MI_PASS",  ""), "MI"),
        ("admin_mts", os.getenv("ADMIN_MTS_PASS", ""), "MTs"),
        ("admin_ra",  os.getenv("ADMIN_RA_PASS",  ""), "RA"),
    ]

    conn = get_conn()
    cur = conn.cursor()
    for username, password, unit in admins:
        if not password:
            print(f"[DB] Password admin '{username}' kosong di .env, di-skip.")
            continue
        cur.execute("SELECT id, password_hash FROM admin WHERE username = ?", (username,))
        row = cur.fetchone()
        if row:
            if not bcrypt.verify(password, row["password_hash"]):
                hashed = bcrypt.hash(password)
                cur.execute(
                    "UPDATE admin SET password_hash = ? WHERE username = ?",
                    (hashed, username)
                )
                print(f"[DB] Password admin '{username}' diperbarui.")
        else:
            hashed = bcrypt.hash(password)
            cur.execute(
                "INSERT INTO admin (username, password_hash, unit) VALUES (?, ?, ?)",
                (username, hashed, unit)
            )
            print(f"[DB] Admin '{username}' untuk unit {unit} dibuat.")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_admin()