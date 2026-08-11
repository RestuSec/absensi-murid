import secrets
import sqlite3
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
from env_loader import load_env
load_env()

DB_PATH = os.path.join(os.path.dirname(__file__), "absensi.db")


def new_token() -> str:
    return secrets.token_urlsafe(16)


def _schema_sql(cur, table):
    return (cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
              .fetchone()[0] or "")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Tabel guru (didaftarkan oleh admin; telegram_id opsional untuk bot)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS guru (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            token TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            mapel TEXT NOT NULL,
            unit TEXT NOT NULL CHECK(unit IN ('MI', 'MTs', 'RA')),
            jabatan TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Migration: tambah kolom token/jabatan & buat telegram_id nullable pada DB lama
    cols = [r[1] for r in cur.execute("PRAGMA table_info(guru)").fetchall()]
    if "token" not in cols or "jabatan" not in cols or "telegram_id INTEGER UNIQUE NOT NULL" in _schema_sql(cur, "guru"):
        # Rebuild tabel biar schema baru (token + jabatan + telegram_id nullable)
        cur.execute("ALTER TABLE guru RENAME TO guru_old")
        cur.execute("""
            CREATE TABLE guru (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                token TEXT UNIQUE NOT NULL,
                nama TEXT NOT NULL,
                mapel TEXT NOT NULL,
                unit TEXT NOT NULL CHECK(unit IN ('MI', 'MTs', 'RA')),
                jabatan TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        cur.execute("""
            INSERT INTO guru (id, telegram_id, nama, mapel, unit, token, created_at)
            SELECT id, telegram_id, nama, mapel, unit, 'legacy-' || telegram_id, created_at
            FROM guru_old
        """)
        cur.execute("DROP TABLE guru_old")
        for row in cur.execute("SELECT id, telegram_id FROM guru").fetchall():
            idsrc = row["telegram_id"] if row["telegram_id"] is not None else f"g{row['id']}"
            cur.execute("UPDATE guru SET token = ? WHERE id = ?", (f"legacy-{idsrc}", row["id"]))
        conn.commit()

    # Tabel absensi
    cur.execute("""
        CREATE TABLE IF NOT EXISTS absensi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guru_id INTEGER NOT NULL,
            nama TEXT NOT NULL,
            mapel TEXT NOT NULL,
            unit TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Hadir', 'Izin', 'Sakit')),
            latitude REAL,
            longitude REAL,
            jam TEXT NOT NULL,
            tanggal TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (guru_id) REFERENCES guru(id)
        )
    """)

    # Hapus duplikat (sisakan yang paling awal), lalu kunci 1 absen/hari per guru.
    cur.execute("""
        DELETE FROM absensi WHERE id NOT IN (
            SELECT MIN(id) FROM absensi GROUP BY guru_id, tanggal
        )
    """)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_absen_1perday ON absensi(guru_id, tanggal)"
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
