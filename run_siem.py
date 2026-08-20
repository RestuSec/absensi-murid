"""Run absensi server + tee output to access.log for SIEM monitoring."""
import subprocess, sys, os, threading
from pathlib import Path

LOGFILE = Path(__file__).parent / "access.log"
SERVE = Path(__file__).parent / "backend" / "serve.py"

os.environ["PORT"] = "8001"

proc = subprocess.Popen(
    [sys.executable, str(SERVE)],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True, bufsize=1,
)

with open(LOGFILE, "a", encoding="utf-8") as f:
    for line in proc.stdout:
        print(line, end="")
        f.write(line)
        f.flush()
