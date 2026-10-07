"""ADM-01 local owner authentication and authorization boundary."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import re
import secrets
from threading import Lock
from time import monotonic
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request
from fastapi import Header

from elton_database.repositories.admin import AdminRepository
from elton_database.session import get_session
from elton_api.catalog.schemas import MAX_MINOR


PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("local-demo-dummy-password-that-is-never-a-credential")


@dataclass(frozen=True)
class AdminPrincipal:
    id: UUID
    session_id: UUID
    permissions: frozenset[str]
    email: str = ""
    expires_at: datetime | None = None


class AdminLoginLimiter:
    """Bounded in-process limiter for the explicitly local demo."""
    def __init__(self) -> None:
        self.lock = Lock()
        self.windows: dict[str, deque[float]] = {}

    def check(self, identity: str, limit: int) -> None:
        now = monotonic()
        with self.lock:
            for key in list(self.windows):
                while self.windows[key] and self.windows[key][0] <= now - 60:
                    self.windows[key].popleft()
                if not self.windows[key]:
                    del self.windows[key]
            if identity not in self.windows and len(self.windows) >= 4096:
                raise HTTPException(429, detail="RATE_LIMITED", headers={"Retry-After": "60"})
            window = self.windows.setdefault(identity, deque())
            if len(window) >= limit:
                raise HTTPException(429, detail="RATE_LIMITED", headers={"Retry-After": "60"})
            window.append(now)


def admin_proof_hash(proof: str) -> str:
    return hashlib.sha256(proof.encode()).hexdigest()


def admin_csrf_token(session_id: UUID, runtime_key: str) -> str:
    return hmac.new(runtime_key.encode(), f"admin:{session_id}".encode(), hashlib.sha256).hexdigest()


def valid_admin_csrf(token: str | None, session_id: UUID, runtime_key: str) -> bool:
    return isinstance(token, str) and token.isascii() and hmac.compare_digest(token, admin_csrf_token(session_id, runtime_key))


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("admin password must be 12 through 128 characters")
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(PASSWORD_HASHER.verify(password_hash, password))
    except (VerificationError, InvalidHashError):
        return False


def _session_cookie(request: Request) -> str | None:
    return request.cookies.get("elton_admin")


def require_admin_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.admin_origins:
        raise HTTPException(403, detail="FORBIDDEN")


def _principal_from_proof(request: Request, proof: str) -> AdminPrincipal:
    sessions = get_session(request.app.state.settings.database_url.get_secret_value())
    try:
        session = next(sessions)
        with session.begin():
            row = AdminRepository(session).active_session(admin_proof_hash(proof))
            if row is None:
                raise HTTPException(401, detail="SESSION_REQUIRED")
            admin_session, admin_user = row
            return AdminPrincipal(admin_user.id, admin_session.id, AdminRepository(session).permissions(admin_user.id), admin_user.email_normalized, admin_session.expires_at)
    finally:
        sessions.close()


def resolve_admin(request: Request) -> AdminPrincipal:
    proof = _session_cookie(request)
    if not proof or len(proof) > 256:
        raise HTTPException(401, detail="SESSION_REQUIRED")
    return _principal_from_proof(request, proof)


def require_admin(request: Request, permission: str) -> AdminPrincipal:
    principal = resolve_admin(request)
    if permission not in principal.permissions:
        raise HTTPException(403, detail="FORBIDDEN")
    return principal


def require_admin_mutation(request: Request, permission: str) -> AdminPrincipal:
    # Browsers omit Origin on safe same-origin GET requests.  Origin remains
    # mandatory for every state-changing admin operation.
    require_admin_origin(request)
    principal = require_admin(request, permission)
    if not valid_admin_csrf(request.headers.get("x-csrf-token"), principal.session_id, request.app.state.settings.session_csrf_key.get_secret_value()):
        raise HTTPException(403, detail="CSRF_REJECTED")
    return principal


def admin_dependency(permission: str, *, mutation: bool = False):
    def dependency(request: Request) -> AdminPrincipal:
        return require_admin_mutation(request, permission) if mutation else require_admin(request, permission)
    return dependency


def issue_login(request: Request, *, email: str, password: str, session) -> tuple[AdminPrincipal, str]:
    require_admin_origin(request)
    limiter: AdminLoginLimiter = request.app.state.admin_login_limiter
    source = request.client.host if request.client else "unknown"
    limiter.check(f"ip:{source}", request.app.state.settings.admin_login_limit_per_minute)
    limiter.check(f"email:{email}", request.app.state.settings.admin_login_limit_per_minute)
    repo = AdminRepository(session)
    owner = repo.owner_by_email(email)
    valid = verify_password(owner.password_hash if owner is not None and owner.active else DUMMY_PASSWORD_HASH, password)
    if owner is None or not owner.active or not valid:
        raise HTTPException(401, detail="INVALID_CREDENTIALS")
    old = _session_cookie(request)
    if old and len(old) <= 256:
        repo.revoke_token(admin_proof_hash(old))
    proof = secrets.token_urlsafe(32)
    record = repo.issue_session(admin_user_id=owner.id, token_hash=admin_proof_hash(proof), ttl_seconds=request.app.state.settings.admin_session_ttl_seconds)
    repo.audit(actor_id=owner.id, action="admin.auth.login", entity_type="admin_session", entity_id=record.id, change_summary={"result": "issued"}, trace_id=getattr(request.state, "trace_id", None))
    return AdminPrincipal(owner.id, record.id, repo.permissions(owner.id), owner.email_normalized, record.expires_at), proof


def revoke_current_session(request: Request, principal: AdminPrincipal, session) -> None:
    proof = _session_cookie(request)
    if proof and len(proof) <= 256:
        AdminRepository(session).revoke_token(admin_proof_hash(proof))
    AdminRepository(session).audit(actor_id=principal.id, action="admin.auth.logout", entity_type="admin_session", entity_id=principal.session_id, change_summary={"result": "revoked"}, trace_id=getattr(request.state, "trace_id", None))


def admin_if_match(if_match: str | None = Header(default=None, alias="If-Match")) -> int:
    if if_match is None:
        raise HTTPException(428, detail="PRECONDITION_REQUIRED")
    if not re.fullmatch(r'"[1-9][0-9]{0,18}"', if_match) or int(if_match[1:-1]) > MAX_MINOR:
        raise HTTPException(422, detail="VALIDATION_ERROR")
    return int(if_match[1:-1])
