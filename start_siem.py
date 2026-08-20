"""Start server with access logging for SIEM monitoring.
Does NOT modify any existing website files.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from serve import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=True)
