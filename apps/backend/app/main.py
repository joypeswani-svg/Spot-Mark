"""
main.py — TruthLens FastAPI Application Entry Point

Step 2:   Extension is wired to backend. Endpoints return rich stub data.
Step 3+:  Real ML pipeline replaces stubs progressively.

All API keys are read from environment variables (via config.py).
No secrets are ever hardcoded here.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.routers import analyze, report, block, trending, community, auth


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and Shutdown lifecycle handlers.
    """
    print(f"[TruthLens] Starting backend — environment: {settings.ENVIRONMENT}")
    print(f"[TruthLens] CORS: {'ALL origins (dev mode)' if settings.ALLOW_ALL_ORIGINS_IN_DEV and settings.ENVIRONMENT == 'development' else settings.CORS_ORIGINS}")
    yield
    print("[TruthLens] Shutting down.")


# ── App Factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="TruthLens API",
    description=(
        "Backend for the TruthLens fake news, deepfake, and AI-image detection system. "
        "Shared by the Chrome/Edge extension and the React Native mobile app.\n\n"
        "**Step 2 status:** Extension wired to backend. Endpoints return rich stub data. "
        "Real ML pipeline begins in Step 3."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Dev: allow ALL origins (including chrome-extension:// URLs from the extension).
# Production: restrict to specific origins listed in CORS_ORIGINS env var.

_is_dev = settings.ENVIRONMENT == "development"
_allow_all = _is_dev and settings.ALLOW_ALL_ORIGINS_IN_DEV

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else [o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=not _allow_all,   # credentials not compatible with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-TruthLens-Job-Id", "X-TruthLens-Cached", "X-TruthLens-Latency-Ms"],
)

# ── GZip compression ──────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=500)

# ── Request timing middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def add_timing_header(request: Request, call_next) -> Response:
    """Adds X-TruthLens-Latency-Ms header to every response for client perf tracking."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-TruthLens-Latency-Ms"] = str(elapsed_ms)
    return response


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(analyze.router,    prefix="/api", tags=["Analysis"])
app.include_router(report.router,     prefix="/api", tags=["Report"])
app.include_router(block.router,      prefix="/api", tags=["Block"])
app.include_router(trending.router,   prefix="/api", tags=["Trending"])
app.include_router(community.router,  prefix="/api", tags=["Community"])
app.include_router(auth.router,       prefix="/api/auth", tags=["Auth"])


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/ping", status_code=204, tags=["Health"])
async def ping():
    """Fast ping probe for extension offline check."""
    return Response(status_code=204)


@app.get("/health", tags=["Health"])
async def health():
    """Simple liveness probe for Docker Compose, load balancers, and the extension."""
    return {
        "status": "ok",
        "version": "0.2.0",
        "environment": settings.ENVIRONMENT,
        "step": 2,
        "capabilities": {
            "analyze_text":  "wired-stub",   # Step 3: real LLM pipeline
            "analyze_image": "stub",         # Step 8
            "analyze_video": "stub",         # Step 9
            "analyze_audio": "stub",         # Step 9
        },
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "TruthLens API",
        "docs": "/docs",
        "health": "/health",
        "version": "0.2.0",
    }
