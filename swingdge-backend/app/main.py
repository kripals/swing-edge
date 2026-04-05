from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.api import auth, portfolio, triggers

settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing needed — Supabase is always on, no connection pool to warm
    yield
    # Shutdown: nothing to clean up


# ── App factory ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SwingEdge API",
    description="Swing trading research and portfolio app for Wealthsimple TFSA accounts",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,  # Hide docs in prod
    redoc_url=None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Middleware (order matters — outermost first) ───────────────────────────────

# 1. CORS — must be first so preflight requests are handled before auth
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# 2. Request ID middleware — adds X-Request-ID header for tracing
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# 3. Cold-start indicator header — lets frontend know this was a fresh wake
_first_request = True

@app.middleware("http")
async def cold_start_header(request: Request, call_next):
    global _first_request
    response = await call_next(request)
    if _first_request:
        response.headers["X-Cold-Start"] = "true"
        _first_request = False
    return response


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(triggers.router)


# ── Health check (no auth — used by Render + GitHub Actions) ─────────────────

@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
