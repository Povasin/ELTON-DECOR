"""Database access for the protected admin boundary."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from elton_database.models.admin import AdminPermission, AdminSession, AdminUser, AuditLog, admin_permissions, audit_log


class AdminRepository:
    def __init__(self, session: Session):
        self.session = session

    def active_session(self, token_hash: str) -> tuple[AdminSession, AdminUser] | None:
        row = self.session.execute(
            select(AdminSession, AdminUser)
            .join(AdminUser, AdminUser.id == AdminSession.admin_user_id)
            .where(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.now(timezone.utc),
                AdminUser.active.is_(True),
            )
        ).first()
        return row

    def permissions(self, admin_user_id: UUID) -> frozenset[str]:
        return frozenset(self.session.scalars(select(AdminPermission.permission).where(AdminPermission.admin_user_id == admin_user_id)))

    def owner_by_email(self, email_normalized: str) -> AdminUser | None:
        return self.session.scalar(select(AdminUser).where(AdminUser.email_normalized == email_normalized))

    def owner_count(self) -> int:
        from sqlalchemy import func
        return int(self.session.scalar(select(func.count()).select_from(AdminUser)) or 0)

    def create_owner(self, *, email_normalized: str, password_hash: str) -> AdminUser:
        owner = AdminUser(id=uuid4(), email_normalized=email_normalized, password_hash=password_hash, active=True)
        self.session.add(owner)
        self.session.flush()
        self.session.execute(insert(admin_permissions), [
            {"admin_user_id": owner.id, "permission": permission}
            for permission in ("catalog.read", "catalog.write", "drafts.read")
        ])
        return owner

    def issue_session(self, *, admin_user_id: UUID, token_hash: str, ttl_seconds: int) -> AdminSession:
        record = AdminSession(
            id=uuid4(), admin_user_id=admin_user_id, token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def revoke_token(self, token_hash: str) -> None:
        record = self.session.scalar(select(AdminSession).where(AdminSession.token_hash == token_hash).with_for_update())
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)

    def revoke_all_sessions(self, admin_user_id: UUID) -> None:
        from sqlalchemy import update
        self.session.execute(update(AdminSession).where(AdminSession.admin_user_id == admin_user_id, AdminSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))

    def audit(self, *, actor_id: UUID, action: str, entity_type: str, entity_id: UUID | None, change_summary: dict, trace_id: str | None) -> None:
        self.session.execute(insert(audit_log).values(
            id=uuid4(), actor_type="admin", actor_id=actor_id, action=action,
            entity_type=entity_type, entity_id=entity_id,
            change_summary=change_summary, trace_id=trace_id,
        ))
