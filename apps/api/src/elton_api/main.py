"""Local foundation API; provider capabilities remain disconnected."""

from contextlib import closing
from uuid import uuid4
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from elton_database.session import get_session
from elton_api.capabilities import CapabilitiesDTO
from elton_api.config import Settings
from elton_api.catalog.routes import router as catalog_router
from elton_api.cart.routes import router as cart_router
from elton_api.drafts.routes import router as draft_router
from elton_api.admin.routes import router as admin_router
from elton_api.admin.auth import AdminLoginLimiter
from elton_api.media.routes import public_router as public_media_router, router as media_router
from elton_api.media.video_processor import VIDEO_RUNTIME_HELP, VideoValidationError, verify_video_runtime
from elton_api.guest.routes import GuestCreationLimiter, router as guest_router


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Elton Decor Foundation API", version="0.1.0")
    app.state.settings = settings
    try:
        verify_video_runtime(
            ffmpeg_binary=settings.ffmpeg_binary, ffprobe_binary=settings.ffprobe_binary,
            timeout_seconds=settings.video_processing_timeout_seconds,
        )
    except VideoValidationError:
        app.state.video_runtime_available = False
        logging.getLogger(__name__).warning(VIDEO_RUNTIME_HELP)
    else:
        app.state.video_runtime_available = True
    app.state.guest_creation_limiter = GuestCreationLimiter()
    app.state.admin_login_limiter = AdminLoginLimiter()

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        request.state.trace_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.trace_id
        if request.url.path.startswith("/api/v1/"):
            private = request.url.path.startswith(("/api/v1/cart", "/api/v1/session", "/api/v1/guest-sessions", "/api/v1/draft-quotes", "/api/v1/checkout-drafts", "/api/v1/admin"))
            response.headers["Cache-Control"] = "private, no-store" if private else "no-store"
        return response

    def problem(request: Request, status: int, code: str, headers=None) -> JSONResponse:
        # Fixed text only; never echo SQL, raw input, cookies or credentials.
        detail = VIDEO_RUNTIME_HELP if code == "CAPABILITY_DISABLED" and request.url.path.endswith("/media") else "The request could not be completed."
        return JSONResponse({"type": f"urn:elton:problem:{code}", "title": code, "status": status, "code": code, "detail": detail, "trace_id": request.state.trace_id, "retryable": status == 503}, status_code=status, headers=headers, media_type="application/problem+json")

    @app.exception_handler(HTTPException)
    async def http_problem(request: Request, exception: HTTPException):
        code = exception.detail if isinstance(exception.detail, str) and exception.detail.isupper() else {404: "NOT_FOUND", 401: "SESSION_REQUIRED", 403: "FORBIDDEN"}.get(exception.status_code, "VALIDATION_ERROR")
        return problem(request, exception.status_code, code, exception.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, exception: RequestValidationError):
        return problem(request, 422, "VALIDATION_ERROR")

    @app.exception_handler(SQLAlchemyError)
    async def storage_problem(request: Request, exception: SQLAlchemyError):
        return problem(request, 503, "STORAGE_TEMPORARILY_UNAVAILABLE")

    app.include_router(catalog_router)
    app.include_router(guest_router)
    app.include_router(cart_router)
    app.include_router(draft_router)
    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(public_media_router)

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"], responses={503: {"description": "PostgreSQL unavailable"}})
    def ready() -> JSONResponse:
        try:
            with closing(get_session(settings.database_url.get_secret_value())) as sessions:
                session = next(sessions)
                session.execute(text("SELECT 1")).scalar_one()
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    @app.get("/api/v1/capabilities", response_model=CapabilitiesDTO, tags=["foundation"])
    def capabilities() -> CapabilitiesDTO:
        return CapabilitiesDTO()

    return app


def app_factory() -> FastAPI:
    """uv run uvicorn elton_api.main:app_factory --factory --host 127.0.0.1."""
    return create_app(Settings())
