from collections import deque
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from elton_api.guest.csrf import require_origin
from elton_api.guest.schemas import SessionDTO
from elton_api.guest.service import GuestPrincipal, create_guest, database_session, resolve_guest, session_dto

router = APIRouter(prefix="/api/v1", tags=["guest"])


class GuestCreationLimiter:
    """Bounded process-local demo limiter; no production distributed guarantee."""
    def __init__(self):
        self.lock = Lock()
        self.windows: dict[str, deque[float]] = {}

    def check(self, identity: str, limit: int) -> None:
        now = monotonic()
        with self.lock:
            for key in list(self.windows):
                if not self.windows[key] or self.windows[key][-1] <= now - 60:
                    del self.windows[key]
            if identity not in self.windows and len(self.windows) >= 4096:
                raise HTTPException(429, detail="RATE_LIMITED", headers={"Retry-After": "60"})
            window = self.windows.setdefault(identity, deque())
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= limit:
                raise HTTPException(429, detail="RATE_LIMITED", headers={"Retry-After": "60"})
            window.append(now)


def allow_guest_creation(request: Request) -> None:
    require_origin(request)
    request.app.state.guest_creation_limiter.check(request.client.host if request.client else "unknown", request.app.state.settings.guest_creation_limit_per_minute)


@router.post("/guest-sessions", response_model=SessionDTO, status_code=201, dependencies=[Depends(allow_guest_creation)], responses={200: {"model": SessionDTO}, 403: {"description": "Origin rejected"}, 429: {"description": "Rate limited"}})
def guest_sessions(request: Request, response: Response, session: Session = Depends(database_session, scope="function")) -> SessionDTO:
    principal, proof = create_guest(request, session)
    if proof is None:
        response.status_code = 200
    else:
        # This slice only runs explicit loopback HTTP; public hosts get Secure.
        secure = not (request.url.scheme == "http" and request.url.hostname in {"localhost", "127.0.0.1", "::1"})
        response.set_cookie("elton_guest", proof, path="/api", max_age=request.app.state.settings.guest_session_ttl_seconds, httponly=True, secure=secure, samesite="lax")
    return session_dto(request, principal)


@router.get("/session", response_model=SessionDTO)
def guest_session(request: Request, principal: GuestPrincipal = Depends(resolve_guest, scope="function")) -> SessionDTO:
    return session_dto(request, principal)
