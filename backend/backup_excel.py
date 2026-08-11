"""Backup penuh database (semua tabel) ke satu file Excel.
Jalankan: ../venv/bin/python backup_excel.py   (dari folder backend)
Output: backups/backup_YYYYMMDD_HHMMSS.xlsx
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_conn

import openpyxl

def main():
    conn = get_conn()
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    summary = []
    for tbl in tables:
        rows = cur.execute(f"SELECT * FROM {tbl}").fetchall()
        ws = wb.create_sheet(title=tbl[:31])
        if rows:
            ws.append(list(rows[0].keys()))
            for r in rows:
                ws.append(list(r))
        summary.append(f"{tbl}: {len(rows)} baris")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
    wb.save(out)
    conn.close()
    print("Backup selesai:", out)
    print("Isi:", ", ".join(summary))

if __name__ == "__main__":
    main()
