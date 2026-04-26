# ─────────────────────────────────────────────────────────────────────────────
#  Run from the PROJECT ROOT (ai-media-automation/), NOT from console/:
#    cd ai-media-automation
#    uvicorn console.backend.main:app --port 8080 --reload
# ─────────────────────────────────────────────────────────────────────────────
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from console.backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("console")


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Console API started")
    yield
    logger.info("Console API stopped")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Media Console API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ORIGIN,
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Audit middleware ─────────────────────────────────────────────────────────

try:
    from console.backend.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
except Exception:
    pass

# ─── Routers ──────────────────────────────────────────────────────────────────

def register_routers():
    """Register all API routers. Import errors are caught individually so a
    missing router doesn't prevent the rest of the app from starting."""
    from console.backend.routers import auth, scraper, scripts

    app.include_router(auth.router, prefix="/api")
    app.include_router(scraper.router, prefix="/api")
    app.include_router(scripts.router, prefix="/api")

    try:
        from console.backend.routers import niches
        app.include_router(niches.router, prefix="/api")
    except ImportError:
        pass

    # Remaining routers added in later sprints:
    try:
        from console.backend.routers import production
        app.include_router(production.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import uploads
        app.include_router(uploads.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import pipeline
        app.include_router(pipeline.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import llm
        app.include_router(llm.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import performance
        app.include_router(performance.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import system
        app.include_router(system.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import credentials
        app.include_router(credentials.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import channels
        app.include_router(channels.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import music
        app.include_router(music.router, prefix="/api")
    except ImportError:
        pass


register_routers()

# ─── WebSocket ────────────────────────────────────────────────────────────────

try:
    from console.backend.ws.pipeline_ws import router as ws_router
    app.include_router(ws_router)
except ImportError:
    pass

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "env": settings.ENV,
    }
