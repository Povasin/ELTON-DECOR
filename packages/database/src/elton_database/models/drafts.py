"""Local saved snapshots; no commercial orders or payment/delivery facts."""
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from .catalog import Base, pk, quantity_check, timestamp
from . import guest  # registers cart/session FK targets


def totals_checks(prefix):
    return [CheckConstraint("currency = 'RUB'", name=f"ck_{prefix}_currency"),
            CheckConstraint("goods_total_minor >= 0", name=f"ck_{prefix}_goods_total"),
            CheckConstraint("delivery_minor IS NULL AND payable_total_minor IS NULL", name=f"ck_{prefix}_no_commerce_totals")]


def totals_columns():
    return [Column("currency", String(3), nullable=False, server_default="RUB"),
            Column("goods_total_minor", BigInteger, nullable=False),
            Column("delivery_minor", BigInteger), Column("payable_total_minor", BigInteger)]


draft_quotes = Table("draft_quotes", Base.metadata, pk(),
    Column("guest_session_id", UUID(as_uuid=True), ForeignKey("guest_sessions.id", ondelete="RESTRICT"), nullable=False),
    Column("cart_id", UUID(as_uuid=True), nullable=False), Column("cart_version", BigInteger, nullable=False),
    Column("state", String, nullable=False, server_default="valid"), *totals_columns(),
    Column("expires_at", DateTime(timezone=True), nullable=False), Column("consumed_by_draft_id", UUID(as_uuid=True)),
    Column("snapshot_json", JSONB, nullable=False), Column("catalog_signature", String, nullable=False),
    UniqueConstraint("id", "guest_session_id", name="uq_quote_owner"),
    ForeignKeyConstraint(["cart_id", "guest_session_id"], ["carts.id", "carts.guest_session_id"], name="fk_quote_cart_owner", ondelete="RESTRICT"),
    ForeignKeyConstraint(["consumed_by_draft_id", "guest_session_id"], ["checkout_drafts.id", "checkout_drafts.guest_session_id"], name="fk_quote_consumed_draft_owner", use_alter=True),
    CheckConstraint("state IN ('valid', 'consumed')", name="ck_quote_state"),
    CheckConstraint("cart_version > 0", name="ck_quote_cart_version"), *totals_checks("quote"))
Index("ix_quote_cart_expiry", draft_quotes.c.cart_id, draft_quotes.c.expires_at)
checkout_drafts = Table("checkout_drafts", Base.metadata, pk(),
    Column("guest_session_id", UUID(as_uuid=True), ForeignKey("guest_sessions.id", ondelete="RESTRICT"), nullable=False),
    Column("quote_id", UUID(as_uuid=True), nullable=False, unique=True),
    Column("state", String, nullable=False, server_default="saved"), Column("channel", String, nullable=False, server_default="site"),
    *totals_columns(), Column("contact_snapshot", JSONB, nullable=False), Column("address_snapshot", JSONB, nullable=False), timestamp("created_at"),
    UniqueConstraint("id", "guest_session_id", name="uq_draft_owner"),
    UniqueConstraint("guest_session_id", "id", name="uq_draft_principal_id"),
    ForeignKeyConstraint(["quote_id", "guest_session_id"], ["draft_quotes.id", "draft_quotes.guest_session_id"], name="fk_draft_quote_owner", ondelete="RESTRICT"),
    CheckConstraint("state = 'saved'", name="ck_draft_saved_only"), CheckConstraint("channel = 'site'", name="ck_draft_site_only"), *totals_checks("draft"))
Index("ix_draft_created_id", checkout_drafts.c.created_at, checkout_drafts.c.id)
Index("ix_draft_guest_created", checkout_drafts.c.guest_session_id, checkout_drafts.c.created_at)
draft_items = Table("draft_items", Base.metadata, pk(),
    Column("draft_id", UUID(as_uuid=True), ForeignKey("checkout_drafts.id", ondelete="RESTRICT"), nullable=False),
    Column("position", Integer, nullable=False), Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
    Column("sku_snapshot", String, nullable=False), Column("title_snapshot", String, nullable=False),
    Column("quantity", Integer, nullable=False), Column("unit_price_minor", BigInteger, nullable=False), Column("line_total_minor", BigInteger, nullable=False),
    Column("bundle_version_id", UUID(as_uuid=True)),
    ForeignKeyConstraint(["bundle_version_id", "product_id"], ["bundle_versions.id", "bundle_versions.product_id"], name="fk_draft_item_bundle_owner", ondelete="RESTRICT"),
    UniqueConstraint("draft_id", "position", name="uq_draft_item_position"),
    UniqueConstraint("draft_id", "sku_snapshot", name="uq_draft_item_sku"),
    quantity_check("quantity", "ck_draft_item_quantity"),
    CheckConstraint("unit_price_minor > 0 AND line_total_minor > 0 AND line_total_minor = unit_price_minor::numeric * quantity", name="ck_draft_item_total"))
draft_components = Table("draft_components", Base.metadata, pk(),
    Column("draft_item_id", UUID(as_uuid=True), ForeignKey("draft_items.id", ondelete="RESTRICT"), nullable=False),
    Column("component_product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
    Column("sku_snapshot", String, nullable=False), Column("title_snapshot", String, nullable=False),
    Column("quantity_per_bundle", Integer, nullable=False), Column("total_quantity", Integer, nullable=False), Column("base_unit_price_minor", BigInteger, nullable=False),
    UniqueConstraint("draft_item_id", "sku_snapshot", name="uq_draft_component_sku"),
    quantity_check("quantity_per_bundle", "ck_draft_component_quantity_per_bundle"), quantity_check("total_quantity", "ck_draft_component_total_quantity"),
    CheckConstraint("base_unit_price_minor > 0", name="ck_draft_component_base_price"))
idempotency_records = Table("idempotency_records", Base.metadata, pk(),
    Column("principal_id", UUID(as_uuid=True), nullable=False), Column("operation", String, nullable=False),
    Column("key_hash", String, nullable=False), Column("request_hash", String, nullable=False),
    Column("draft_id", UUID(as_uuid=True), nullable=False), Column("response_status", Integer, nullable=False), timestamp("created_at"),
    UniqueConstraint("principal_id", "operation", "key_hash", name="uq_idempotency_scope"),
    ForeignKeyConstraint(["principal_id", "draft_id"], ["checkout_drafts.guest_session_id", "checkout_drafts.id"], name="fk_idempotency_draft_owner", deferrable=True, initially="DEFERRED", ondelete="RESTRICT"),
    CheckConstraint("response_status = 201", name="ck_idempotency_response"))


class DraftQuote(Base):
    __table__ = draft_quotes


class CheckoutDraft(Base):
    __table__ = checkout_drafts


class DraftItem(Base):
    __table__ = draft_items


class DraftComponent(Base):
    __table__ = draft_components


class IdempotencyRecord(Base):
    __table__ = idempotency_records
