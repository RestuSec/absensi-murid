# backend/auth_seed.py
# ── Seed Phrase + Recovery Key Security Module ────────────────────────────────
import secrets
import hashlib
import json
import os
from typing import List, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# ── Wordlist BIP-39 (resmi, 2048 kata) ───────────────────────────────────────
BIP39_PATH = os.path.join(os.path.dirname(__file__), "wordlist_bip39.txt")
with open(BIP39_PATH, "r", encoding="utf-8") as _f:
    WORDLIST = [w for w in (l.strip() for l in _f) if w]
assert len(WORDLIST) == 2048, f"wordlist harus 2048 kata, ternyata {len(WORDLIST)}"

# ── Mapping Barang (bantuan hafalan nomor → barang rumah tangga) ─────────────
ITEMS = [
    "rumah", "kamar", "kasur", "meja", "kursi", "lemari", "pintu",
    "jendela", "lampu", "kulkas", "oven", "tv", "telepon", "gelas",
    "cangkir", "sendok", "garpu", "alarm", "sepeda", "mobil", "kipas",
    "charger", "mouse", "keyboard", "monitor", "cpu", "printer",
    "speaker", "gorden", "kalem", "beranda", "halaman", "pekarangan"
]

ph = PasswordHasher()

# ── BIP-39 Mnemonic (128-bit entropy + SHA256 checksum → 12 kata valid) ───────
def generate_seed_phrase() -> List[str]:
    """Generate 12 kata BIP-39 asli: 128-bit entropy + 4-bit checksum.
    Kata ke-12 adalah checksum sungguhan — kata2 lain + urutan valid
    jika kata ke-12 cocok dengan SHA256(entropy)."""
    entropy = secrets.token_bytes(16)          # 128 bit
    h = hashlib.sha256(entropy).digest()
    checksum_bits = (len(entropy) * 8) // 32    # 4 bit
    entropy_int = int.from_bytes(entropy, "big")
    checksum_int = h[0] >> (8 - checksum_bits)
    bits = (entropy_int << checksum_bits) | checksum_int   # 132 bit
    indices = [(bits >> (11 * (12 - 1 - i))) & 0x7FF for i in range(12)]
    return [WORDLIST[i] for i in indices]

def verify_seed_words(seed_words: List[str]) -> bool:
    """Periksa BIP-39: 12 kata valid + kata ke-12 benar untuk 11 kata awal."""
    if len(seed_words) != 12:
        return False
    try:
        indices = [WORDLIST.index(w.strip().lower()) for w in seed_words]
    except ValueError:
        return False
    bits = 0
    for i in indices:
        bits = (bits << 11) | i
    checksum_len = 4
    entropy_bits = len(indices) * 11 - checksum_len
    entropy_int = bits >> checksum_len
    entropy = entropy_int.to_bytes(entropy_bits // 8, "big")
    checksum_int = (bits & ((1 << checksum_len) - 1))
    h = hashlib.sha256(entropy).digest()
    expected = h[0] >> (8 - checksum_len)
    return expected == checksum_int

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
    Generate challenge: tanya kata seed di posisi acak.
    (Versi baru: bertanya KATA SEED, bukan daftar ITEMS publik — tidak bisa
    ditebak oleh yang tidak hafal seed.)
    """
    nomor = secrets.randbelow(len(mapping)) + 1
    kata = mapping[nomor-1][1]

    return {
        "question": f"Apa kata ke-{nomor} dari seed phrase kamu?",
        "answer": kata,
        "nomor": nomor,
        "seed_index": nomor - 1
    }
