"""FastAPI main application."""

import json
import os
import random
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from app.api.endpoints import ads, auth, analytics, campaigns, creative, predictions, lp_analysis, rankings, notifications, competitive_intel, meta_marketing, media, data_quality, ai_chat, rankings_notifications, integrations
from app.api.endpoints import settings as settings_endpoints
from app.api.graphql import router as graphql_router
from app.api.v2 import router as v2_router
from app.core.config import get_settings
from app.core.gateway_auth import is_gateway_authorized, is_protected_path
from app.core.response_compression import (
    choose_encoding,
    compress_payload,
    is_compressible_content_type,
    merge_vary_accept_encoding,
)
from app.core.response_case import with_dual_case_keys
from app.core.trace import reset_current_trace_id, set_current_trace_id

logger = structlog.get_logger()
settings = get_settings()

# C71: structured request log sampling policy
REQUEST_LOG_SAMPLE_RATES = {
    "success": 0.05,      # 2xx/3xx
    "client_error": 0.25, # 4xx
}
REQUEST_SLOW_MS = 1000


def _resolve_request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id")
    if rid:
        return rid
    existing = getattr(request.state, "request_id", None)
    if existing:
        return str(existing)
    generated = str(uuid.uuid4())
    request.state.request_id = generated
    return generated


def _error_body(
    code: str,
    message: str,
    request_id: str,
    details: list | None = None,
    category: str | None = None,
) -> dict:
    error = {
        "code": code,
        "message": message,
        "request_id": request_id,
        "details": details or [],
    }
    if category:
        error["category"] = category
    return {
        "error": {
            **error,
        }
    }


def _classify_exception(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    mod = getattr(type(exc), "__module__", "").lower()
    if "validation" in name:
        return "user"
    if "httpx" in mod or "requests" in mod or "socket" in mod or "timeout" in name:
        return "external"
    return "system"


def _request_log_reason(status_code: int, elapsed_ms: float) -> str | None:
    """Return sampling reason or None when this request should be skipped."""
    # Always keep server errors and slow requests
    if status_code >= 500:
        return "server_error"
    if elapsed_ms >= REQUEST_SLOW_MS:
        return "slow_request"

    if 400 <= status_code < 500:
        if random.random() < REQUEST_LOG_SAMPLE_RATES["client_error"]:
            return "sampled_client_error"
        return None

    if random.random() < REQUEST_LOG_SAMPLE_RATES["success"]:
        return "sampled_success"
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("application_starting", env=settings.app_env)

    # Security checks
    if not settings.is_secret_key_secure:
        if settings.app_env == "production":
            logger.critical(
                "insecure_secret_key",
                message="SECRET_KEY is insecure! Set a strong random string (>=32 chars) via SECRET_KEY env var.",
            )
            raise RuntimeError(
                "本番環境でデフォルトのSECRET_KEYは使用できません。"
                "SECRET_KEY環境変数に32文字以上のランダム文字列を設定してください。"
            )
        else:
            logger.warning(
                "insecure_secret_key",
                message="SECRET_KEY is using the default value. Set SECRET_KEY env var for production.",
            )

    if "*" in settings.cors_origins_list and settings.app_env == "production":
        logger.warning(
            "cors_wildcard_in_production",
            message="CORS_ORIGINS='*' in production. Set specific origins for security.",
        )

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
        import app.models.crawl_job  # noqa: F401
        import app.models.campaign  # noqa: F401
        import app.models.meta_ad_account  # noqa: F401
        import app.models.meta_campaign  # noqa: F401
        import app.models.ab_test  # noqa: F401
        import app.models.optimization  # noqa: F401
        import app.models.alert_rule  # noqa: F401
        import app.models.alert_history  # noqa: F401
        import app.models.conversation  # noqa: F401
        import app.models.data_quality  # noqa: F401
        Base.metadata.create_all(bind=sync_engine)
        from app.core.database import _run_migrations
        _run_migrations(sync_engine)
        logger.info("database_tables_ensured")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    yield

    # Shutdown: cleanup resources gracefully
    logger.info("application_shutting_down")
    try:
        from app.core.database import async_engine
        await async_engine.dispose()
        logger.info("database_connections_closed")
    except Exception as e:
        logger.warning("database_cleanup_error", error=str(e))


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
    responses={
        422: {"description": "Validation Error", "model": __import__('app.schemas.error', fromlist=['ErrorResponse']).ErrorResponse},
        500: {"description": "Internal Server Error", "model": __import__('app.schemas.error', fromlist=['ErrorResponse']).ErrorResponse},
    },
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
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=422,
        content=_error_body(
            "validation_error",
            "リクエストの検証に失敗しました",
            request_id,
            details,
            category="user",
        ),
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Catch database errors — log full traceback, return generic message."""
    logger.error("database_error", error=str(exc), path=request.url.path)
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            "database_error",
            "データベースエラーが発生しました",
            request_id,
            category="system",
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    logger.error("unhandled_error", error=str(exc), error_type=type(exc).__name__, path=request.url.path)
    message = str(exc) if settings.debug else "内部サーバーエラーが発生しました"
    request_id = _resolve_request_id(request)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            "internal_error",
            message,
            request_id,
            category=_classify_exception(exc),
        ),
    )


# ==================== Middleware ====================


# Request timing middleware
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    import time
    request.state.request_id = _resolve_request_id(request)
    trace_token = set_current_trace_id(request.state.request_id)

    try:
        if settings.api_gateway_auth_enabled and is_protected_path(
            request.url.path,
            settings.api_gateway_protected_prefixes_list,
        ):
            if not is_gateway_authorized(request, settings.api_gateway_api_keys_list):
                return JSONResponse(
                    status_code=401,
                    content=_error_body(
                        "gateway_auth_required",
                        "API gateway authentication required",
                        request.state.request_id,
                        category="user",
                    ),
                )

        start = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Trace-ID"] = request.state.request_id
        response.headers["X-Response-Time"] = f"{elapsed:.0f}ms"
        # CI-092: SLO violation detection
        from app.core.slo import check_slo_violation
        check_slo_violation(request.url.path, elapsed, response.status_code)
        if elapsed > REQUEST_SLOW_MS:
            logger.warning("slow_request", path=request.url.path, method=request.method, elapsed_ms=round(elapsed))

        reason = _request_log_reason(response.status_code, elapsed)
        if reason:
            logger.info(
                "request_log",
                sample_reason=reason,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                elapsed_ms=round(elapsed, 2),
                query_present=bool(request.url.query),
                user_agent=(request.headers.get("user-agent") or "")[:120],
                request_id=request.state.request_id,
                client_ip=request.client.host if request.client else None,
            )

        content_type = (response.headers.get("content-type") or "").lower()
        has_set_cookie = "set-cookie" in response.headers
        is_json = "application/json" in content_type

        if settings.api_dual_case_output and is_json and not has_set_cookie:
            try:
                body_chunks = [chunk async for chunk in response.body_iterator]
                raw_body = b"".join(body_chunks)
                parsed = json.loads(raw_body.decode("utf-8")) if raw_body else None
                if isinstance(parsed, (dict, list)):
                    transformed = with_dual_case_keys(parsed)
                    new_headers = dict(response.headers)
                    new_headers.pop("content-length", None)
                    new_headers.pop("Content-Length", None)
                    response = JSONResponse(
                        content=transformed,
                        status_code=response.status_code,
                        headers=new_headers,
                        media_type="application/json",
                        background=response.background,
                    )
            except Exception:
                # Fail-open: never block API responses due to case conversion.
                pass

        compression_content_type = (response.headers.get("content-type") or "").lower()
        if (
            settings.api_compression_enabled
            and request.method != "HEAD"
            and 200 <= response.status_code < 300
            and "content-encoding" not in response.headers
            and is_compressible_content_type(compression_content_type)
        ):
            selected_encoding = choose_encoding(
                request.headers.get("accept-encoding", ""),
                allow_brotli=settings.api_compression_brotli_enabled,
                allow_gzip=settings.api_compression_gzip_enabled,
            )
            if selected_encoding:
                try:
                    body_chunks = [chunk async for chunk in response.body_iterator]
                    raw_body = b"".join(body_chunks)
                    if len(raw_body) >= settings.api_compression_min_size_bytes:
                        compressed_body = compress_payload(
                            raw_body,
                            selected_encoding,
                            gzip_level=settings.api_compression_gzip_level,
                            brotli_quality=settings.api_compression_brotli_quality,
                        )
                        headers = dict(response.headers)
                        headers["Content-Encoding"] = selected_encoding
                        headers["Vary"] = merge_vary_accept_encoding(headers.get("Vary"))
                        headers.pop("Content-Length", None)
                        headers.pop("content-length", None)
                        response = Response(
                            content=compressed_body,
                            status_code=response.status_code,
                            headers=headers,
                            media_type=compression_content_type.split(";", 1)[0].strip(),
                            background=response.background,
                        )
                except Exception:
                    # Fail-open: never block API responses due to compression errors.
                    pass

        if request.url.path.startswith(settings.api_v1_prefix):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "Mon, 30 Jun 2026 23:59:59 GMT"
            response.headers["Link"] = f'</api/docs>; rel="successor-version"'
        return response
    finally:
        reset_current_trace_id(trace_token)


# CORS middleware — configure via CORS_ORIGINS env var (default "*" for development)
# In production, set CORS_ORIGINS to specific domains (e.g. "https://d3qlbagx7gq5sp.cloudfront.net")
_cors_origins = settings.cors_origins_list
_allow_credentials = "*" not in _cors_origins  # credentials require explicit origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
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
API_V2_PREFIX = settings.api_v2_prefix
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(ads.router, prefix=API_PREFIX)
app.include_router(campaigns.router, prefix=API_PREFIX)
app.include_router(creative.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(lp_analysis.router, prefix=API_PREFIX)
app.include_router(rankings.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(competitive_intel.router, prefix=API_PREFIX)
app.include_router(meta_marketing.router, prefix=API_PREFIX)
app.include_router(settings_endpoints.router, prefix=API_PREFIX)
app.include_router(media.router, prefix=API_PREFIX)
app.include_router(data_quality.router, prefix=API_PREFIX)
app.include_router(ai_chat.router, prefix=API_PREFIX)
app.include_router(rankings_notifications.router, prefix=API_PREFIX)
app.include_router(integrations.router, prefix=API_PREFIX)
app.include_router(graphql_router, prefix=API_PREFIX)
app.include_router(v2_router, prefix=API_V2_PREFIX)


@app.get("/")
async def root():
    return {
        "name": "Video Ad Analysis AI Platform",
        "version": "1.0.0",
        "docs": "/api/docs",
        "api_versions": [settings.api_v1_prefix, settings.api_v2_prefix],
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    """Enhanced health check — verifies database connectivity.

    Registered at both /health (direct) and /api/health (via CloudFront /api/* routing).
    """
    from app.core.database import SyncSessionLocal, is_in_memory_mode, get_connection_error

    result: dict = {"status": "healthy", "in_memory_mode": is_in_memory_mode()}

    if is_in_memory_mode():
        result["database"] = "in_memory"
        conn_err = get_connection_error()
        if conn_err:
            result["database_error"] = conn_err
        result["status"] = "degraded"
    else:
        try:
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

    # Skip Redis/Celery checks in Lambda environment
    is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if is_lambda:
        result["runtime"] = "lambda"
    else:
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_timeout=2)
            r.ping()
            result["redis"] = "ok"
        except Exception:
            result["redis"] = "unavailable"

        # Celery worker check
        try:
            from app.tasks.worker import celery_app
            inspect = celery_app.control.inspect(timeout=1.0)
            ping_result = inspect.ping()
            if ping_result:
                result["celery_workers"] = len(ping_result)
            else:
                result["celery_workers"] = 0
                result["status"] = "degraded"
        except Exception:
            result["celery_workers"] = "unavailable"

    return result
