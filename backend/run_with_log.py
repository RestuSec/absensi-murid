"""Wrapper that runs serve.py and logs to a file simultaneously."""
import subprocess
import sys
import time
from pathlib import Path

LOGFILE = Path(__file__).parent / "access.log"
SERVE = Path(__file__).parent / "serve.py"

proc = subprocess.Popen(
    [sys.executable, str(SERVE)],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

print(f"Server started, logging to {LOGFILE}")

with open(LOGFILE, "a", encoding="utf-8") as f:
    for line in proc.stdout:
        print(line, end="")
        f.write(line)
        f.flush()
