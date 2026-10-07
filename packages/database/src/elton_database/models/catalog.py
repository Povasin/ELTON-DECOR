"""Stage 1 PostgreSQL catalog. Alembic alone owns schema creation."""
from uuid import uuid4

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Column, DateTime,
                        ForeignKey, ForeignKeyConstraint, Index, Integer,
                        String, Table, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def pk():
    return Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4)


def version():
    return Column("version", BigInteger, nullable=False, server_default="1")


def timestamp(name):
    return Column(name, DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


def json_column(name):
    return Column(name, JSONB, nullable=False, server_default=text("'{}'::jsonb"))


def quantity_check(column, name):
    return CheckConstraint(f"{column} BETWEEN 1 AND 2147483647", name=name)


products = Table(
    "products", Base.metadata, pk(), Column("sku", String, nullable=False, unique=True),
    Column("slug", String, nullable=False, unique=True), Column("type", String, nullable=False),
    Column("title", Text, nullable=False), Column("description", Text, nullable=False, server_default=""),
    Column("active", Boolean, nullable=False, server_default=text("true")), version(),
    json_column("attributes_json"), json_column("seo_json"),
    Column("current_bundle_version_id", UUID(as_uuid=True), nullable=True),
    CheckConstraint("type IN ('single', 'bundle')", name="ck_products_type"),
    CheckConstraint("version > 0", name="ck_products_version"),
    ForeignKeyConstraint(["current_bundle_version_id", "id"], ["bundle_versions.id", "bundle_versions.product_id"], name="fk_product_current_bundle_owner", use_alter=True),
)
Index("ix_products_active", products.c.active)

categories = Table("categories", Base.metadata, pk(), Column("slug", String, nullable=False, unique=True), Column("title", Text, nullable=False), Column("sort_order", Integer, nullable=False, server_default="0"))
product_categories = Table("product_categories", Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), primary_key=True))
Index("ix_product_categories_category", product_categories.c.category_id)
collections = Table("collections", Base.metadata, pk(), Column("slug", String, nullable=False, unique=True), Column("title", Text, nullable=False), Column("sort_order", Integer, nullable=False, server_default="0"))
collection_items = Table("collection_items", Base.metadata,
    Column("collection_id", UUID(as_uuid=True), ForeignKey("collections.id", ondelete="RESTRICT"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("position", Integer, nullable=False, server_default="0"))
product_relations = Table("product_relations", Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("related_product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True))
site_prices = Table("site_prices", Base.metadata,
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("amount_minor", BigInteger, nullable=False), Column("currency", String(3), nullable=False, server_default="RUB"),
    Column("original_amount_minor", BigInteger, nullable=True),
    version(), timestamp("updated_at"), CheckConstraint("amount_minor > 0", name="ck_site_price_positive"),
    CheckConstraint("original_amount_minor IS NULL OR original_amount_minor > 0", name="ck_site_price_original_positive"),
    CheckConstraint("original_amount_minor IS NULL OR original_amount_minor >= amount_minor", name="ck_site_price_original_not_below_current"),
    CheckConstraint("currency = 'RUB'", name="ck_site_price_currency"), CheckConstraint("version > 0", name="ck_site_price_version"))
bundle_versions = Table("bundle_versions", Base.metadata, pk(),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
    Column("number", BigInteger, nullable=False), timestamp("created_at"),
    UniqueConstraint("id", "product_id", name="uq_bundle_version_owner"),
    UniqueConstraint("product_id", "number", name="uq_bundle_product_number"),
    CheckConstraint("number > 0", name="ck_bundle_version_number"))
bundle_components = Table("bundle_components", Base.metadata,
    Column("version_id", UUID(as_uuid=True), ForeignKey("bundle_versions.id", ondelete="RESTRICT"), primary_key=True),
    Column("component_product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("quantity", Integer, nullable=False), quantity_check("quantity", "ck_bundle_component_quantity"))
product_media = Table("product_media", Base.metadata, pk(),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
    Column("storage_key", String, nullable=False, unique=True), Column("media_type", String, nullable=False),
    Column("scan_state", String, nullable=False, server_default="quarantined"),
    Column("position", Integer, nullable=False, server_default="0"), Column("alt_text", Text, nullable=False, server_default=""), json_column("metadata_json"),
    CheckConstraint("media_type IN ('image', 'video')", name="ck_product_media_type"),
    CheckConstraint("scan_state IN ('quarantined', 'clean', 'rejected')", name="ck_product_media_scan"))


class Product(Base):
    __table__ = products


class Category(Base):
    __table__ = categories


class SitePrice(Base):
    __table__ = site_prices


class BundleVersion(Base):
    __table__ = bundle_versions


class BundleComponent(Base):
    __table__ = bundle_components


class ProductMedia(Base):
    __table__ = product_media


class Collection(Base):
    __table__ = collections
