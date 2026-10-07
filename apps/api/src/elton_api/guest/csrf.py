"""Session-bound CSRF; authentication proof is a separate random secret."""
import hashlib
import hmac
from uuid import UUID

from fastapi import HTTPException, Request


def csrf_token(session_id: UUID, runtime_key: str) -> str:
    return hmac.new(runtime_key.encode(), f"guest:{session_id}".encode(), hashlib.sha256).hexdigest()


def valid_csrf(token: str | None, session_id: UUID, runtime_key: str) -> bool:
    return isinstance(token, str) and token.isascii() and hmac.compare_digest(token, csrf_token(session_id, runtime_key))


def require_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.guest_origins:
        raise HTTPException(403, detail="FORBIDDEN")


def require_csrf(request: Request, principal) -> None:
    require_origin(request)
    key = request.app.state.settings.session_csrf_key.get_secret_value()
    if not valid_csrf(request.headers.get("x-csrf-token"), principal.id, key):
        raise HTTPException(403, detail="CSRF_REJECTED")
