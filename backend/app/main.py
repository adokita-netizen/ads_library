"""FastAPI main application."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.endpoints import ads, auth, analytics, creative, predictions, lp_analysis, rankings, notifications, competitive_intel
from app.api.endpoints import settings as settings_endpoints
from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("application_starting", env=settings.app_env)

    # Auto-create tables if they don't exist (development convenience)
    try:
        from app.core.database import sync_engine, Base
        # Import all models so Base.metadata has them registered
        import app.models.ad  # noqa: F401
        import app.models.ad_metrics  # noqa: F401
        import app.models.analysis  # noqa: F401
        import app.models.user  # noqa: F401
        import app.models.landing_page  # noqa: F401
        import app.models.api_key  # noqa: F401
        Base.metadata.create_all(bind=sync_engine)
        logger.info("database_tables_ensured")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    yield

    # Shutdown: cleanup resources
    logger.info("application_shutting_down")


app = FastAPI(
    title="Video Ad Analysis AI Platform",
    description=(
        "動画広告分析AIプラットフォーム - "
        "競合広告の収集・分析・生成を統合した自社向けソリューション"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ==================== Global Exception Handlers ====================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return structured 422 for Pydantic / query-param validation errors."""
    details = []
    for err in exc.errors():
        details.append({
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "リクエストの検証に失敗しました", "details": details}},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Catch database errors — log full traceback, return generic message."""
    logger.error("database_error", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "database_error", "message": "データベースエラーが発生しました", "details": []}},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    logger.error("unhandled_error", error=str(exc), error_type=type(exc).__name__, path=request.url.path)
    message = str(exc) if settings.debug else "内部サーバーエラーが発生しました"
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": message, "details": []}},
    )


# ==================== Middleware ====================


# Request timing middleware
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    import time
    start = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - start) * 1000
    response.headers["X-Response-Time"] = f"{elapsed:.0f}ms"
    if elapsed > 1000:
        logger.warning("slow_request", path=request.url.path, method=request.method, elapsed_ms=round(elapsed))
    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
if settings.enable_metrics:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except ImportError:
        pass

# Include API routers
API_PREFIX = settings.api_v1_prefix
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(ads.router, prefix=API_PREFIX)
app.include_router(creative.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(lp_analysis.router, prefix=API_PREFIX)
app.include_router(rankings.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(competitive_intel.router, prefix=API_PREFIX)
app.include_router(settings_endpoints.router, prefix=API_PREFIX)


@app.get("/")
async def root():
    return {
        "name": "Video Ad Analysis AI Platform",
        "version": "1.0.0",
        "docs": "/api/docs",
    }


@app.get("/health")
def health_check():
    """Enhanced health check — verifies database connectivity."""
    result: dict = {"status": "healthy"}
    try:
        from app.core.database import SyncSessionLocal
        session = SyncSessionLocal()
        try:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
            result["database"] = "ok"
        finally:
            session.close()
    except Exception as e:
        result["database"] = "error"
        result["database_error"] = str(e)
        result["status"] = "degraded"

    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        result["redis"] = "ok"
    except Exception:
        result["redis"] = "unavailable"

    return result
