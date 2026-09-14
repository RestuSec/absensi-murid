# backend/auth_seed.py
# ── Seed Phrase + Recovery Key Security Module ────────────────────────────────
import secrets
import json
from typing import List, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# ── Wordlist & Mapping Barang ─────────────────────────────────────────────────
# Kamu bisa custom sesuai gaya hidupmu. Ini contoh.
WORDLIST = [
    "kopi", "meja", "kursi", "pintu", "jendela", "lampu", "buku",
    "pena", "kucing", "anjing", "burung", "ikan", "kulkas", "oven",
    "tv", "telepon", "gelas", "cangkir", "sendok", "garpu", "alarm",
    "sepeda", "mobil", "jemput", "makan", "minum", "tidur", "bangun",
    "mandi", "sapu", "kamar", "kasur", "lemari", "kalem", "beranda",
    "halaman", "pekarangan", "gorden", "blinds", "kipas", "stopkontak",
    "kabel", "charger", "mouse", "keyboard", "monitor", "cpu", "printer",
    "speaker", "aturan", "resolusi", "kelulusan", "raport", "ujian"
]

ITEMS = [
    "rumah", "kamar", "kasur", "meja", "kursi", "lemari", "pintu",
    "jendela", "lampu", "kulkas", "oven", "tv", "telepon", "gelas",
    "cangkir", "sendok", "garpu", "alarm", "sepeda", "mobil", "kipas",
    "charger", "mouse", "keyboard", "monitor", "cpu", "printer",
    "speaker", "gorden", "kalem", "beranda", "halaman", "pekarangan"
]

ph = PasswordHasher()

# ── Seed Phrase Functions ─────────────────────────────────────────────────────
def generate_seed_phrase() -> List[str]:
    """Generate 12 kata random dari WORDLIST."""
    return [secrets.choice(WORDLIST) for _ in range(12)]

def build_mapping(seed: List[str]) -> List[Tuple[int, str, str]]:
    """
    Build mapping: [(nomor, kata_seed, barang), ...]
    Contoh: [(1, 'kopi', 'rumah'), (2, 'meja', 'kamar'), ...]
    """
    mapping = []
    for i, word in enumerate(seed, 1):
        barang = ITEMS[(i-1) % len(ITEMS)]
        mapping.append((i, word, barang))
    return mapping

def hash_seed(seed: List[str]) -> str:
    """Hash seed phrase pakai argon2."""
    return ph.hash(" ".join(seed))

def verify_seed(stored_hash: str, seed_input: str) -> bool:
    """Verifikasi seed phrase user vs hash yang disimpan."""
    try:
        ph.verify(stored_hash, seed_input)
        return True
    except VerifyMismatchError:
        return False

# ── Recovery Key Functions ────────────────────────────────────────────────────
def generate_recovery_key(length: int = 64) -> str:
    """Generate recovery key acak (64 karakter, tidak expired)."""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
    return ''.join(secrets.choice(chars) for _ in range(length))

def hash_recovery_key(key: str) -> str:
    """Hash recovery key pakai argon2."""
    return ph.hash(key)

def verify_recovery_key(stored_hash: str, key_input: str) -> bool:
    """Verifikasi recovery key."""
    try:
        ph.verify(stored_hash, key_input)
        return True
    except VerifyMismatchError:
        return False

# ── Challenge Generator ───────────────────────────────────────────────────────
def generate_challenge(mapping: List[Tuple[int, str, str]]) -> dict:
    """
    Generate challenge random:
    - Tipe A: "Barang di nomor berapa?" → jawab nomor
    - Tipe B: "Di nomor berapa ada apa?" → jawab barang
    """
    tipe = secrets.choice(["A", "B"])
    nomor = secrets.randbelow(len(mapping)) + 1
    _, kata, barang = mapping[nomor-1]

    if tipe == "A":
        question = f"Nomor berapa '{barang}'?"
        answer = str(nomor)
    else:
        question = f"Di nomor {nomor} ada apa?"
        answer = barang

    return {
        "question": question,
        "answer": answer,
        "tipe": tipe,
        "nomor": nomor,
        "seed_index": nomor - 1
    }
