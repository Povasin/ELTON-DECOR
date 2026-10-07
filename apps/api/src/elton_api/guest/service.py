"""Resolve only live random guest proof, never a submitted resource UUID."""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from elton_database.repositories.guest import GuestRepository
from elton_database.session import get_session
from elton_api.guest.csrf import csrf_token
from elton_api.guest.schemas import SessionDTO


@dataclass(frozen=True)
class GuestPrincipal:
    id: UUID
    expires_at: datetime


def database_session(request: Request) -> Iterator[Session]:
    sessions = get_session(request.app.state.settings.database_url.get_secret_value())
    try:
        session = next(sessions)
        with session.begin():
            yield session
    finally:
        sessions.close()


def proof_hash(proof: str) -> str:
    return hashlib.sha256(proof.encode()).hexdigest()


def lookup_guest(request: Request, session: Session) -> GuestPrincipal | None:
    proof = request.cookies.get("elton_guest")
    if not proof:
        return None
    if len(proof) > 256:
        raise HTTPException(401, detail="SESSION_REQUIRED")
    guest = GuestRepository(session).by_hash(proof_hash(proof))
    if guest is None:
        raise HTTPException(401, detail="SESSION_REQUIRED")
    if guest.revoked_at is not None or guest.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, detail="SESSION_EXPIRED")
    return GuestPrincipal(guest.id, guest.expires_at)


def resolve_guest(request: Request, session: Session = Depends(database_session, scope="function")) -> GuestPrincipal:
    principal = lookup_guest(request, session)
    if principal is None:
        raise HTTPException(401, detail="SESSION_REQUIRED")
    return principal


def create_guest(request: Request, session: Session) -> tuple[GuestPrincipal, str | None]:
    # Live sessions are reused. A stale or unknown proof may come from a local
    # database that was reset, so replace it with a new anonymous session.
    try:
        principal = lookup_guest(request, session)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        principal = None
    if principal:
        return principal, None
    proof = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=request.app.state.settings.guest_session_ttl_seconds)
    guest = GuestRepository(session).create(proof_hash(proof), expires)
    return GuestPrincipal(guest.id, guest.expires_at), proof


def session_dto(request: Request, principal: GuestPrincipal) -> SessionDTO:
    return SessionDTO(csrf_token=csrf_token(principal.id, request.app.state.settings.session_csrf_key.get_secret_value()), expires_at=principal.expires_at)
