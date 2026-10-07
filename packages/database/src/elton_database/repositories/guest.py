"""Guest scope only. Caller owns the transaction and proof hashing."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from elton_database.models.guest import Cart, GuestSession


class GuestRepository:
    def __init__(self, session: Session):
        self.session = session

    def by_hash(self, token_hash: str) -> GuestSession | None:
        # Keep a resolved principal live through the transaction; revoke waits.
        return self.session.scalar(select(GuestSession).where(GuestSession.token_hash == token_hash).with_for_update(read=True))

    def create(self, token_hash: str, expires_at: datetime) -> GuestSession:
        guest = GuestSession(id=uuid4(), token_hash=token_hash, expires_at=expires_at)
        self.session.add(guest)
        self.session.flush()
        self.session.add(Cart(id=uuid4(), guest_session_id=guest.id, version=1))
        self.session.flush()
        return guest
