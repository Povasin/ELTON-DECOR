"""Protected administration persistence.

The tables deliberately contain no bootstrap identity or credentials.  A later
ADM-01 decision may provision an administrator through a controlled process.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .catalog import Base, json_column, pk, timestamp


admin_users = Table(
    "admin_users", Base.metadata, pk(),
    Column("email_normalized", String(254), nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    timestamp("created_at"),
)

admin_sessions = Table(
    "admin_sessions", Base.metadata, pk(),
    Column("admin_user_id", UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False),
    Column("token_hash", String(128), nullable=False, unique=True),
    timestamp("created_at"),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
)
Index("ix_admin_sessions_user_active", admin_sessions.c.admin_user_id, admin_sessions.c.expires_at, postgresql_where=admin_sessions.c.revoked_at.is_(None))

admin_permissions = Table(
    "admin_permissions", Base.metadata,
    Column("admin_user_id", UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
    Column("permission", String(64), primary_key=True),
    CheckConstraint("permission IN ('catalog.read', 'catalog.write', 'drafts.read')", name="ck_admin_permission_name"),
)

audit_log = Table(
    "audit_log", Base.metadata, pk(),
    Column("actor_type", String(32), nullable=False, server_default="admin"),
    Column("actor_id", UUID(as_uuid=True), ForeignKey("admin_users.id", ondelete="RESTRICT")),
    Column("action", String(96), nullable=False),
    Column("entity_type", String(64), nullable=False),
    Column("entity_id", UUID(as_uuid=True)),
    json_column("change_summary"),
    Column("trace_id", String(128)),
    timestamp("created_at"),
    CheckConstraint("actor_type = 'admin'", name="ck_audit_actor_type"),
)
Index("ix_audit_entity_created", audit_log.c.entity_type, audit_log.c.entity_id, audit_log.c.created_at)


class AdminUser(Base):
    __table__ = admin_users


class AdminSession(Base):
    __table__ = admin_sessions


class AdminPermission(Base):
    __table__ = admin_permissions


class AuditLog(Base):
    __table__ = audit_log
