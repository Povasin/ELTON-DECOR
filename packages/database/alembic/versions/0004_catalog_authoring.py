"""Catalog authoring fields for the local admin editor.

The migration is additive: existing site prices keep their current value and
simply have no compare-at price until an administrator sets one.
"""
from alembic import op


revision = "0004_catalog_authoring"
down_revision = "0003_admin_access"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE site_prices ADD COLUMN original_amount_minor BIGINT")
    op.execute(
        "ALTER TABLE site_prices ADD CONSTRAINT ck_site_price_original_positive "
        "CHECK (original_amount_minor IS NULL OR original_amount_minor > 0)"
    )
    op.execute(
        "ALTER TABLE site_prices ADD CONSTRAINT ck_site_price_original_not_below_current "
        "CHECK (original_amount_minor IS NULL OR original_amount_minor >= amount_minor)"
    )


def downgrade():
    op.execute("ALTER TABLE site_prices DROP CONSTRAINT ck_site_price_original_not_below_current")
    op.execute("ALTER TABLE site_prices DROP CONSTRAINT ck_site_price_original_positive")
    op.execute("ALTER TABLE site_prices DROP COLUMN original_amount_minor")
