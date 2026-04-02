import logging
import os
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import allowed_origins, env_flag, get_admin_secret, parse_rate_limit_specs
from app.db import SessionLocal, engine
from app.logging_utils import configure_logging, request_id_var
from app.routers.admin import router as admin_router
from app.routers.auth import router as auth_router
from app.routers.classes import router as classes_router
from app.routers.lesson import router as lesson_router
from app.routers.students import router as students_router
from app.services.auth_service import auth_required, ensure_bootstrap_users, validate_auth_configuration
from app.services.kokoro_tts_service import KokoroTtsError, TTS_CACHE_DIR, prune_tts_cache, warmup_tts_runtime
from app.services.rate_limit_service import DEFAULT_RATE_LIMIT_SPECS, InMemoryRateLimiter

configure_logging()
logger = logging.getLogger(__name__)
TTS_PREWARM_ENABLED = os.getenv("LUMINOS_TTS_PREWARM_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
TTS_STRICT_STARTUP = os.getenv("LUMINOS_TTS_STRICT_STARTUP", "false").lower() in {"1", "true", "yes", "on"}
TTS_PRUNE_ON_STARTUP = os.getenv("LUMINOS_TTS_CACHE_PRUNE_ON_STARTUP", "true").lower() in {"1", "true", "yes", "on"}
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
ENFORCE_ADMIN_SECRET = env_flag("LUMINOS_ENFORCE_ADMIN_SECRET", True)
RATE_LIMIT_SPECS = parse_rate_limit_specs(os.getenv("LUMINOS_RATE_LIMITS", ""), DEFAULT_RATE_LIMIT_SPECS)
rate_limiter = InMemoryRateLimiter(RATE_LIMIT_SPECS)

app = FastAPI(title="LUMINOS Lesson Engine")

origins = allowed_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )


def apply_security_headers(response, scheme: str) -> None:
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "media-src 'self' blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'",
    )
    if scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        client_host = request.client.host if request.client else "unknown"
        token = request_id_var.set(request_id)
        try:
            logger.info("request.start method=%s path=%s client=%s", request.method, request.url.path, client_host)
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            logger.info("request.end method=%s path=%s", request.method, request.url.path)
            request_id_var.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        apply_security_headers(response, request.url.scheme)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in {"/health", "/ready"} or request.url.path.startswith("/static") or request.url.path.startswith("/tts-cache"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        allowed, retry_after, limit = rate_limiter.allow(request.url.path, client_host)
        if not allowed:
            logger.warning("rate_limit.exceeded path=%s client=%s", request.url.path, client_host)
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            response.headers["Retry-After"] = str(retry_after or 1)
            response.headers["X-RateLimit-Limit"] = str(limit or 0)
            apply_security_headers(response, request.url.scheme)
            return response

        response = await call_next(request)
        if limit is not None:
            response.headers.setdefault("X-RateLimit-Limit", str(limit))
        return response


app.add_middleware(RequestContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/tts-cache", StaticFiles(directory=str(TTS_CACHE_DIR)), name="tts-cache")
app.include_router(auth_router)
app.include_router(lesson_router)
app.include_router(students_router)
app.include_router(classes_router)
app.include_router(admin_router)


@app.on_event("startup")
def startup():
    validate_auth_configuration()
    if ENFORCE_ADMIN_SECRET and not get_admin_secret():
        raise RuntimeError("LUMINOS_ADMIN_SECRET must be set before the application starts.")

    if auth_required():
        db = SessionLocal()
        try:
            ensure_bootstrap_users(db)
        finally:
            db.close()

    if SENTRY_DSN:
        try:
            import sentry_sdk
        except ImportError:
            logger.warning("SENTRY_DSN is set but sentry-sdk is not installed.")
        else:
            sentry_sdk.init(dsn=SENTRY_DSN)

    if TTS_PRUNE_ON_STARTUP:
        prune_tts_cache()

    if TTS_PREWARM_ENABLED:
        try:
            warmup_tts_runtime()
        except KokoroTtsError as exc:
            if TTS_STRICT_STARTUP:
                raise
            logger.warning("Kokoro TTS warmup warning: %s", exc)


@app.get("/")
def root():
    if auth_required():
        return RedirectResponse(url="/auth/login")
    return RedirectResponse(url="/lesson/")


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        logger.exception("healthcheck.failed")
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "error", "detail": str(exc)})


@app.get("/ready")
def ready():
    return health()
