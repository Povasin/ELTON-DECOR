"""Frozen Stage 1 PostgreSQL DDL; independent of subsequent model changes."""
from alembic import op

revision = '0001_catalog'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE products (
	id UUID NOT NULL,
	sku VARCHAR NOT NULL,
	slug VARCHAR NOT NULL,
	type VARCHAR NOT NULL,
	title TEXT NOT NULL,
	description TEXT DEFAULT '' NOT NULL,
	active BOOLEAN DEFAULT true NOT NULL,
	version BIGINT DEFAULT '1' NOT NULL,
	attributes_json JSONB DEFAULT '{}'::jsonb NOT NULL,
	seo_json JSONB DEFAULT '{}'::jsonb NOT NULL,
	current_bundle_version_id UUID,
	PRIMARY KEY (id),
	CONSTRAINT ck_products_type CHECK (type IN ('single', 'bundle')),
	CONSTRAINT ck_products_version CHECK (version > 0),
	UNIQUE (sku),
	UNIQUE (slug)
)
""")
    op.execute('CREATE INDEX ix_products_active ON products (active)')
    op.execute("""
CREATE TABLE categories (
	id UUID NOT NULL,
	slug VARCHAR NOT NULL,
	title TEXT NOT NULL,
	sort_order INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
)
""")
    op.execute("""
CREATE TABLE product_categories (
	product_id UUID NOT NULL,
	category_id UUID NOT NULL,
	PRIMARY KEY (product_id, category_id),
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT,
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT
)
""")
    op.execute('CREATE INDEX ix_product_categories_category ON product_categories (category_id)')
    op.execute("""
CREATE TABLE collections (
	id UUID NOT NULL,
	slug VARCHAR NOT NULL,
	title TEXT NOT NULL,
	sort_order INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
)
""")
    op.execute("""
CREATE TABLE collection_items (
	collection_id UUID NOT NULL,
	product_id UUID NOT NULL,
	position INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (collection_id, product_id),
	FOREIGN KEY(collection_id) REFERENCES collections (id) ON DELETE RESTRICT,
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE product_relations (
	product_id UUID NOT NULL,
	related_product_id UUID NOT NULL,
	PRIMARY KEY (product_id, related_product_id),
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT,
	FOREIGN KEY(related_product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE site_prices (
	product_id UUID NOT NULL,
	amount_minor BIGINT NOT NULL,
	currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
	version BIGINT DEFAULT '1' NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (product_id),
	CONSTRAINT ck_site_price_positive CHECK (amount_minor > 0),
	CONSTRAINT ck_site_price_currency CHECK (currency = 'RUB'),
	CONSTRAINT ck_site_price_version CHECK (version > 0),
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE bundle_versions (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	number BIGINT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_bundle_version_owner UNIQUE (id, product_id),
	CONSTRAINT uq_bundle_product_number UNIQUE (product_id, number),
	CONSTRAINT ck_bundle_version_number CHECK (number > 0),
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE bundle_components (
	version_id UUID NOT NULL,
	component_product_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	PRIMARY KEY (version_id, component_product_id),
	CONSTRAINT ck_bundle_component_quantity CHECK (quantity BETWEEN 1 AND 2147483647),
	FOREIGN KEY(version_id) REFERENCES bundle_versions (id) ON DELETE RESTRICT,
	FOREIGN KEY(component_product_id) REFERENCES products (id) ON DELETE RESTRICT
)
""")
    op.execute("""
CREATE TABLE product_media (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	storage_key VARCHAR NOT NULL,
	media_type VARCHAR NOT NULL,
	scan_state VARCHAR DEFAULT 'quarantined' NOT NULL,
	position INTEGER DEFAULT '0' NOT NULL,
	alt_text TEXT DEFAULT '' NOT NULL,
	metadata_json JSONB DEFAULT '{}'::jsonb NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_product_media_type CHECK (media_type IN ('image', 'video')),
	CONSTRAINT ck_product_media_scan CHECK (scan_state IN ('quarantined', 'clean', 'rejected')),
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT,
	UNIQUE (storage_key)
)
""")
    op.execute('ALTER TABLE products ADD CONSTRAINT fk_product_current_bundle_owner FOREIGN KEY(current_bundle_version_id, id) REFERENCES bundle_versions (id, product_id)')


def downgrade():
    op.execute('ALTER TABLE products DROP CONSTRAINT fk_product_current_bundle_owner')
    op.execute('DROP TABLE bundle_components')
    op.execute('DROP TABLE site_prices')
    op.execute('DROP TABLE product_relations')
    op.execute('DROP TABLE product_media')
    op.execute('DROP TABLE product_categories')
    op.execute('DROP TABLE collection_items')
    op.execute('DROP TABLE bundle_versions')
    op.execute('DROP TABLE products')
    op.execute('DROP TABLE collections')
    op.execute('DROP TABLE categories')
