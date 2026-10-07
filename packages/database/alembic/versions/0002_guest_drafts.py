"""Frozen Stage 1 PostgreSQL DDL; independent of subsequent model changes."""
from alembic import op

revision = '0002_guest_drafts'
down_revision = '0001_catalog'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE guest_sessions (
	id UUID NOT NULL,
	token_hash VARCHAR NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (token_hash)
)
""")
    op.execute("""
CREATE TABLE carts (
	id UUID NOT NULL,
	guest_session_id UUID NOT NULL,
	version BIGINT DEFAULT '1' NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_cart_owner UNIQUE (id, guest_session_id),
	CONSTRAINT ck_cart_version CHECK (version > 0),
	UNIQUE (guest_session_id),
	FOREIGN KEY(guest_session_id) REFERENCES guest_sessions (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE cart_items (
	cart_id UUID NOT NULL,
	product_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	PRIMARY KEY (cart_id, product_id),
	CONSTRAINT ck_cart_item_quantity CHECK (quantity BETWEEN 1 AND 2147483647),
	FOREIGN KEY(cart_id) REFERENCES carts (id) ON DELETE RESTRICT,
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE draft_quotes (
	id UUID NOT NULL,
	guest_session_id UUID NOT NULL,
	cart_id UUID NOT NULL,
	cart_version BIGINT NOT NULL,
	state VARCHAR DEFAULT 'valid' NOT NULL,
	currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
	goods_total_minor BIGINT NOT NULL,
	delivery_minor BIGINT,
	payable_total_minor BIGINT,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	consumed_by_draft_id UUID,
	snapshot_json JSONB NOT NULL,
	catalog_signature VARCHAR NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_quote_owner UNIQUE (id, guest_session_id),
	CONSTRAINT fk_quote_cart_owner FOREIGN KEY(cart_id, guest_session_id) REFERENCES carts (id, guest_session_id) ON DELETE RESTRICT,
	CONSTRAINT ck_quote_state CHECK (state IN ('valid', 'consumed')),
	CONSTRAINT ck_quote_cart_version CHECK (cart_version > 0),
	CONSTRAINT ck_quote_currency CHECK (currency = 'RUB'),
	CONSTRAINT ck_quote_goods_total CHECK (goods_total_minor >= 0),
	CONSTRAINT ck_quote_no_commerce_totals CHECK (delivery_minor IS NULL AND payable_total_minor IS NULL),
	FOREIGN KEY(guest_session_id) REFERENCES guest_sessions (id) ON DELETE RESTRICT
)
""")
    op.execute('CREATE INDEX ix_quote_cart_expiry ON draft_quotes (cart_id, expires_at)')
    op.execute("""
CREATE TABLE checkout_drafts (
	id UUID NOT NULL,
	guest_session_id UUID NOT NULL,
	quote_id UUID NOT NULL,
	state VARCHAR DEFAULT 'saved' NOT NULL,
	channel VARCHAR DEFAULT 'site' NOT NULL,
	currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
	goods_total_minor BIGINT NOT NULL,
	delivery_minor BIGINT,
	payable_total_minor BIGINT,
	contact_snapshot JSONB NOT NULL,
	address_snapshot JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_draft_owner UNIQUE (id, guest_session_id),
	CONSTRAINT uq_draft_principal_id UNIQUE (guest_session_id, id),
	CONSTRAINT fk_draft_quote_owner FOREIGN KEY(quote_id, guest_session_id) REFERENCES draft_quotes (id, guest_session_id) ON DELETE RESTRICT,
	CONSTRAINT ck_draft_saved_only CHECK (state = 'saved'),
	CONSTRAINT ck_draft_site_only CHECK (channel = 'site'),
	CONSTRAINT ck_draft_currency CHECK (currency = 'RUB'),
	CONSTRAINT ck_draft_goods_total CHECK (goods_total_minor >= 0),
	CONSTRAINT ck_draft_no_commerce_totals CHECK (delivery_minor IS NULL AND payable_total_minor IS NULL),
	FOREIGN KEY(guest_session_id) REFERENCES guest_sessions (id) ON DELETE RESTRICT,
	UNIQUE (quote_id)
)
""")
    op.execute('CREATE INDEX ix_draft_created_id ON checkout_drafts (created_at, id)')
    op.execute('CREATE INDEX ix_draft_guest_created ON checkout_drafts (guest_session_id, created_at)')
    op.execute("""
CREATE TABLE draft_items (
	id UUID NOT NULL,
	draft_id UUID NOT NULL,
	position INTEGER NOT NULL,
	product_id UUID NOT NULL,
	sku_snapshot VARCHAR NOT NULL,
	title_snapshot VARCHAR NOT NULL,
	quantity INTEGER NOT NULL,
	unit_price_minor BIGINT NOT NULL,
	line_total_minor BIGINT NOT NULL,
	bundle_version_id UUID,
	PRIMARY KEY (id),
	CONSTRAINT fk_draft_item_bundle_owner FOREIGN KEY(bundle_version_id, product_id) REFERENCES bundle_versions (id, product_id) ON DELETE RESTRICT,
	CONSTRAINT uq_draft_item_position UNIQUE (draft_id, position),
	CONSTRAINT uq_draft_item_sku UNIQUE (draft_id, sku_snapshot),
	CONSTRAINT ck_draft_item_quantity CHECK (quantity BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_draft_item_total CHECK (unit_price_minor > 0 AND line_total_minor > 0 AND line_total_minor = unit_price_minor::numeric * quantity),
	FOREIGN KEY(draft_id) REFERENCES checkout_drafts (id) ON DELETE RESTRICT,
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE draft_components (
	id UUID NOT NULL,
	draft_item_id UUID NOT NULL,
	component_product_id UUID NOT NULL,
	sku_snapshot VARCHAR NOT NULL,
	title_snapshot VARCHAR NOT NULL,
	quantity_per_bundle INTEGER NOT NULL,
	total_quantity INTEGER NOT NULL,
	base_unit_price_minor BIGINT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_draft_component_sku UNIQUE (draft_item_id, sku_snapshot),
	CONSTRAINT ck_draft_component_quantity_per_bundle CHECK (quantity_per_bundle BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_draft_component_total_quantity CHECK (total_quantity BETWEEN 1 AND 2147483647),
	CONSTRAINT ck_draft_component_base_price CHECK (base_unit_price_minor > 0),
	FOREIGN KEY(draft_item_id) REFERENCES draft_items (id) ON DELETE RESTRICT,
	FOREIGN KEY(component_product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE idempotency_records (
	id UUID NOT NULL,
	principal_id UUID NOT NULL,
	operation VARCHAR NOT NULL,
	key_hash VARCHAR NOT NULL,
	request_hash VARCHAR NOT NULL,
	draft_id UUID NOT NULL,
	response_status INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_idempotency_scope UNIQUE (principal_id, operation, key_hash),
	CONSTRAINT fk_idempotency_draft_owner FOREIGN KEY(principal_id, draft_id) REFERENCES checkout_drafts (guest_session_id, id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT ck_idempotency_response CHECK (response_status = 201)
)
""")
    op.execute('ALTER TABLE draft_quotes ADD CONSTRAINT fk_quote_consumed_draft_owner FOREIGN KEY(consumed_by_draft_id, guest_session_id) REFERENCES checkout_drafts (id, guest_session_id)')


def downgrade():
    op.execute('ALTER TABLE draft_quotes DROP CONSTRAINT fk_quote_consumed_draft_owner')
    op.execute('DROP TABLE draft_components')
    op.execute('DROP TABLE idempotency_records')
    op.execute('DROP TABLE draft_items')
    op.execute('DROP TABLE checkout_drafts')
    op.execute('DROP TABLE draft_quotes')
    op.execute('DROP TABLE cart_items')
    op.execute('DROP TABLE carts')
    op.execute('DROP TABLE guest_sessions')
