"""Protected admin identity, sessions, permissions and audit storage.

No identity, password or session is inserted.  ADM-01 provisioning remains a
separate reviewed operation.
"""
from alembic import op

revision = "0003_admin_access"
down_revision = "0002_guest_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE admin_users (
    id UUID NOT NULL,
    email_normalized VARCHAR(254) NOT NULL,
    password_hash TEXT NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id), UNIQUE (email_normalized)
)
""")
    op.execute("""
CREATE TABLE admin_sessions (
    id UUID NOT NULL,
    admin_user_id UUID NOT NULL,
    token_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id), UNIQUE (token_hash),
    FOREIGN KEY(admin_user_id) REFERENCES admin_users (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE admin_permissions (
    admin_user_id UUID NOT NULL,
    permission VARCHAR(64) NOT NULL,
    PRIMARY KEY (admin_user_id, permission),
    CONSTRAINT ck_admin_permission_name CHECK (permission IN ('catalog.read', 'catalog.write', 'drafts.read')),
    FOREIGN KEY(admin_user_id) REFERENCES admin_users (id) ON DELETE CASCADE
)
""")
    op.execute("CREATE INDEX ix_admin_sessions_user_active ON admin_sessions (admin_user_id, expires_at) WHERE revoked_at IS NULL")
    op.execute("""
CREATE TABLE audit_log (
    id UUID NOT NULL,
    actor_type VARCHAR(32) DEFAULT 'admin' NOT NULL,
    actor_id UUID,
    action VARCHAR(96) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID,
    change_summary JSONB DEFAULT '{}'::jsonb NOT NULL,
    trace_id VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_audit_actor_type CHECK (actor_type = 'admin'),
    FOREIGN KEY(actor_id) REFERENCES admin_users (id) ON DELETE RESTRICT
)
""")
    op.execute("CREATE INDEX ix_audit_entity_created ON audit_log (entity_type, entity_id, created_at)")


def downgrade():
    op.execute("DROP TABLE audit_log")
    op.execute("DROP INDEX ix_admin_sessions_user_active")
    op.execute("DROP TABLE admin_permissions")
    op.execute("DROP TABLE admin_sessions")
    op.execute("DROP TABLE admin_users")
