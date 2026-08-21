"""
Jalankan ini untuk serve backend + dashboard sekaligus.
FastAPI akan serve dashboard di root (/), API di /api/
"""
import os
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from main import app

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "dashboard")

# Serve static assets
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(DASHBOARD_DIR, "static")),
    name="static_dashboard",
)

# Route HTML pages
@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
def serve_login():
    return FileResponse(os.path.join(DASHBOARD_DIR, "login.html"))

@app.get("/portofolio", include_in_schema=False)
def serve_portofolio():
    return FileResponse(os.path.join(DASHBOARD_DIR, "landing.html"))

@app.get("/dashboard", include_in_schema=False)
@app.get("/index", include_in_schema=False)
def serve_dashboard():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

# Fallback: file HTML apapun di folder dashboard
@app.get("/absen", include_in_schema=False)
def serve_absen():
    return FileResponse(os.path.join(DASHBOARD_DIR, "absen.html"))

@app.get("/{filename}.html", include_in_schema=False)
def serve_html(filename: str):
    if "/" in filename or "\\" in filename or filename in (".", ".."):
        raise HTTPException(status_code=404, detail="Not Found")
    path = os.path.join(DASHBOARD_DIR, f"{filename}.html")
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse(os.path.join(DASHBOARD_DIR, "login.html"))

if __name__ == "__main__":
    import uvicorn
    reload = os.getenv("UVICORN_RELOAD", "0").lower() in ("1", "true", "yes")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("serve:app", host="0.0.0.0", port=port, reload=reload)
