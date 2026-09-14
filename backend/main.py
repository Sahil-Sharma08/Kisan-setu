import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from backend.database import init_db
from backend.seed_data import seed_all
from backend.routers import (
    auth,
    centers,
    commodities,
    bookings,
    queue,
    procurement,
    complaints,
    analytics,
    assistant,
    soil_testing,
    throughput,
    events,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title="KisanSetu Platform API",
    description="Smart Agricultural Procurement & Queue Intelligence Platform — RESTful Microservice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json"
)

# Enable universal CORS for frictionless local and network interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers under /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(centers.router, prefix="/api/v1")
app.include_router(commodities.router, prefix="/api/v1")
app.include_router(bookings.router, prefix="/api/v1")
app.include_router(queue.router, prefix="/api/v1")
app.include_router(procurement.router, prefix="/api/v1")
app.include_router(complaints.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(soil_testing.router, prefix="/api/v1")
app.include_router(throughput.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")

@app.get("/yard-screen", include_in_schema=False)
def yard_screen_view():
    """Direct route for Public Yard Billboard Outdoor TV/Projector Display"""
    screen_path = os.path.join(FRONTEND_DIR, "yard-screen.html")
    if os.path.exists(screen_path):
        return FileResponse(screen_path, media_type="text/html")
    return RedirectResponse(url="/yard-screen.html")

@app.get("/command-center", include_in_schema=False)
def command_center_view():
    """Direct route for Mandi Superintendent Command Center"""
    cmd_path = os.path.join(FRONTEND_DIR, "admin", "superintendent.html")
    if os.path.exists(cmd_path):
        return FileResponse(cmd_path, media_type="text/html")
    return RedirectResponse(url="/admin/superintendent.html")

@app.on_event("startup")
def on_startup():
    """Ensure database schema is created and seeded with realistic demo data on startup"""
    init_db()
    seed_all()

@app.get("/api/v1/health", tags=["System Health"])
def health_check():
    from backend.database import IS_SUPABASE
    db_name = "Supabase PostgreSQL" if IS_SUPABASE else "SQLite (data/kisansetu.db)"
    return {
        "status": "healthy",
        "service": "KisanSetu Backend Engine",
        "version": "1.0.0",
        "database": db_name,
        "is_supabase": IS_SUPABASE,
        "docs": "/docs"
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    svg_path = os.path.join(FRONTEND_DIR, "assets", "logo.svg")
    if os.path.exists(svg_path):
        return FileResponse(svg_path, media_type="image/svg+xml")
    return {"error": "favicon not found"}

# Mount frontend static directory at root
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
