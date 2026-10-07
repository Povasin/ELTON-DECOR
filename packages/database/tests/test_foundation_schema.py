"""Actual PG constraints: removing any tested constraint permits an invalid write.

Offline checks only prove migration generation and synthetic fixture boundaries.
They are never evidence that PostgreSQL accepted the migrations.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "packages/database"


def config(connection=None, output=None):
    assert (DB / "alembic.ini").exists(), "Task 2 migrations are missing"
    cfg = Config(str(DB / "alembic.ini"), output_buffer=output)
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def test_migrations_generate_offline_without_runtime_credentials():
    """Missing revision/DDL or a wrongly immediate FK breaks offline generation."""
    output = io.StringIO()
    command.upgrade(config(output=output), "head", sql=True)
    ddl = output.getvalue()
    assert "CREATE TABLE products" in ddl
    assert "CREATE TABLE checkout_drafts" in ddl
    assert "DEFERRABLE INITIALLY DEFERRED" in ddl
    for forbidden in ("payments", "customers", "fulfillments", "refunds", "reservations", "ledger", "outbox", "inbox"):
        assert f"CREATE TABLE {forbidden}" not in ddl


def test_fixture_is_synthetic_catalog_without_commercial_or_personal_data():
    """Omitted CAT-01 categories or introduced PII/stock/reviews breaks the seed contract."""
    path = DB / "fixtures/catalog.synthetic.json"
    assert path.exists(), "Task 2 synthetic catalog is missing"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["synthetic"] is True
    assert {x["slug"] for x in fixture["categories"]} == {
        "artificial-flowers", "vases", "flowers-in-vase", "paintings", "compositions"
    }
    assert {x["type"] for x in fixture["products"]} == {"single", "bundle"}
    assert any(x.get("components") for x in fixture["products"])
    def inspect(value):
        if isinstance(value, dict):
            assert not set(value) & {"phone", "email", "address", "name", "stock", "stocks", "reviews", "rating", "customer", "token", "secret"}
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(fixture)


@pytest.fixture(scope="module")
def pg_engine():
    url = os.environ.get("ELTON_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Actual PostgreSQL gate incomplete: ELTON_TEST_DATABASE_URL is not supplied; SQLite is not evidence")
    engine = create_engine(url, hide_parameters=True)
    assert engine.dialect.name == "postgresql", "Tests require actual PostgreSQL"
    schema = "test_foundation_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.connect() as conn:
            conn.execute(text(f'SET search_path TO "{schema}"'))
            conn.commit()
            command.upgrade(config(conn), "0001_catalog")
            assert conn.scalar(text("SELECT count(*) FROM products")) == 0
            conn.commit()
            command.upgrade(config(conn), "head")
            conn.commit()
        yield engine, schema
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def pg(pg_engine):
    engine, schema = pg_engine
    with engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{schema}"'))
        conn.commit()
        transaction = conn.begin()
        yield conn
        if transaction.is_active:
            transaction.rollback()


def insert(conn, table, **values):
    columns = ", ".join(values)
    binds = ", ".join(":" + key for key in values)
    conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({binds})"), values)


def setup_cart(conn):
    product, guest, cart = uuid4(), uuid4(), uuid4()
    insert(conn, "products", id=product, sku="TEST-" + product.hex, slug=product.hex, type="single", title="Synthetic")
    insert(conn, "guest_sessions", id=guest, token_hash=guest.hex, expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    insert(conn, "carts", id=cart, guest_session_id=guest)
    return product, guest, cart


@contextmanager
def rejected(conn):
    with pytest.raises(DBAPIError):
        with conn.begin_nested():
            yield


@pytest.mark.postgres
def test_duplicate_sku_and_cart_line_rejected(pg):
    product, _, cart = setup_cart(pg)
    with rejected(pg):
        insert(pg, "products", id=uuid4(), sku="TEST-" + product.hex, slug=uuid4().hex, type="single", title="Duplicate")
    insert(pg, "cart_items", cart_id=cart, product_id=product, quantity=1)
    with rejected(pg):
        insert(pg, "cart_items", cart_id=cart, product_id=product, quantity=1)


@pytest.mark.postgres
@pytest.mark.parametrize("quantity", [0, -1, 2147483648])
def test_invalid_cart_quantity_rejected(pg, quantity):
    product, _, cart = setup_cart(pg)
    with rejected(pg):
        insert(pg, "cart_items", cart_id=cart, product_id=product, quantity=quantity)


@pytest.mark.postgres
def test_referenced_product_cannot_be_hard_deleted(pg):
    product, _, cart = setup_cart(pg)
    insert(pg, "cart_items", cart_id=cart, product_id=product, quantity=1)
    with rejected(pg):
        pg.execute(text("DELETE FROM products WHERE id=:id"), {"id": product})


def saved_draft(conn, guest, cart):
    quote, draft = uuid4(), uuid4()
    insert(conn, "draft_quotes", id=quote, guest_session_id=guest, cart_id=cart, cart_version=1, state="valid", currency="RUB", goods_total_minor=10000, expires_at=datetime.now(timezone.utc) + timedelta(minutes=15), snapshot_json='{"version": 1}', catalog_signature="synthetic-signature")
    insert(conn, "checkout_drafts", id=draft, guest_session_id=guest, quote_id=quote, state="saved", channel="site", currency="RUB", goods_total_minor=20000, contact_snapshot='{}', address_snapshot='{}')
    return quote, draft


@pytest.mark.postgres
def test_idempotency_scope_duplicate_and_nonnull_draft(pg):
    _, guest, cart = setup_cart(pg)
    _, draft = saved_draft(pg, guest, cart)
    values = dict(principal_id=guest, operation="create_checkout_draft", key_hash="hashed-key", request_hash="hashed-body", draft_id=draft, response_status=201)
    insert(pg, "idempotency_records", id=uuid4(), **values)
    with rejected(pg):
        insert(pg, "idempotency_records", id=uuid4(), **values)
    values.update(key_hash="other-hash", draft_id=None)
    with rejected(pg):
        insert(pg, "idempotency_records", id=uuid4(), **values)


@pytest.mark.postgres
def test_missing_deferred_draft_fails_at_commit(pg):
    _, guest, _ = setup_cart(pg)
    insert(pg, "idempotency_records", id=uuid4(), principal_id=guest, operation="create_checkout_draft", key_hash="hash", request_hash="hash", draft_id=uuid4(), response_status=201)
    # INSERT succeeds: the actual commit must reject the unfinished placeholder.
    with pytest.raises(DBAPIError):
        pg.commit()
    pg.rollback()


@pytest.mark.postgres
def test_quote_delivery_total_must_remain_null(pg):
    _, guest, cart = setup_cart(pg)
    quote, _ = saved_draft(pg, guest, cart)
    with rejected(pg):
        pg.execute(text("UPDATE draft_quotes SET delivery_minor=0 WHERE id=:id"), {"id": quote})


@pytest.mark.postgres
def test_draft_requires_matching_quote_owner(pg):
    """Removing the composite quote-owner FK permits a foreign guest's draft."""
    _, owner, cart = setup_cart(pg)
    _, foreign_guest, _ = setup_cart(pg)
    quote, draft = uuid4(), uuid4()
    insert(pg, "draft_quotes", id=quote, guest_session_id=owner, cart_id=cart,
           cart_version=1, state="valid", currency="RUB", goods_total_minor=1,
           expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
           snapshot_json='{}', catalog_signature="synthetic-signature")
    assert pg.scalar(text("SELECT count(*) FROM checkout_drafts WHERE quote_id=:id"), {"id": quote}) == 0
    values = dict(id=draft, guest_session_id=foreign_guest, quote_id=quote,
                  state="saved", channel="site", currency="RUB", goods_total_minor=1,
                  contact_snapshot='{}', address_snapshot='{}')
    with pytest.raises(DBAPIError) as failure:
        with pg.begin_nested():
            insert(pg, "checkout_drafts", **values)
    assert failure.value.orig.sqlstate == "23503"
    assert failure.value.orig.diag.constraint_name == "fk_draft_quote_owner"
    # The identical draft/quote works with its owner, ruling out unrelated constraints.
    insert(pg, "checkout_drafts", **{**values, "guest_session_id": owner})
    assert pg.scalar(text("SELECT guest_session_id FROM checkout_drafts WHERE id=:id"), {"id": draft}) == owner


@pytest.mark.postgres
def test_quote_requires_matching_cart_owner(pg):
    """Removing the composite cart-owner FK permits a foreign guest's quote."""
    _, owner, cart = setup_cart(pg)
    _, foreign_guest, _ = setup_cart(pg)
    quote = uuid4()
    values = dict(id=quote, guest_session_id=foreign_guest, cart_id=cart,
                  cart_version=1, state="valid", currency="RUB", goods_total_minor=1,
                  expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                  snapshot_json='{}', catalog_signature="synthetic-signature")
    with pytest.raises(DBAPIError) as failure:
        with pg.begin_nested():
            insert(pg, "draft_quotes", **values)
    assert failure.value.orig.sqlstate == "23503"
    assert failure.value.orig.diag.constraint_name == "fk_quote_cart_owner"
    insert(pg, "draft_quotes", **{**values, "guest_session_id": owner})
    assert pg.scalar(text("SELECT guest_session_id FROM draft_quotes WHERE id=:id"), {"id": quote}) == owner


@pytest.mark.postgres
def test_positive_prices_and_money_overflow_rejected(pg):
    product, _, _ = setup_cart(pg)
    for amount in (0, -1, 9223372036854775808):
        with rejected(pg):
            insert(pg, "site_prices", product_id=product, amount_minor=amount, currency="RUB")
    with rejected(pg):
        insert(pg, "site_prices", product_id=product, amount_minor=100, currency="USD")


def draft_line(conn):
    product, guest, cart = setup_cart(conn)
    _, draft = saved_draft(conn, guest, cart)
    item = uuid4()
    insert(conn, "draft_items", id=item, draft_id=draft, position=0, product_id=product,
           sku_snapshot="FROZEN-SKU", title_snapshot="Frozen title", quantity=2,
           unit_price_minor=10000, line_total_minor=20000)
    return product, guest, draft, item


@pytest.mark.postgres
@pytest.mark.parametrize("quantity", [0, -1, 2147483648])
def test_bundle_and_snapshot_quantities_rejected(pg, quantity):
    product, _, draft, item = draft_line(pg)
    version = uuid4()
    insert(pg, "bundle_versions", id=version, product_id=product, number=1)
    with rejected(pg):
        insert(pg, "bundle_components", version_id=version, component_product_id=product, quantity=quantity)
    with rejected(pg):
        insert(pg, "draft_items", id=uuid4(), draft_id=draft, position=1, product_id=product,
               sku_snapshot="OTHER", title_snapshot="Other", quantity=quantity,
               unit_price_minor=1, line_total_minor=1)
    for column in ("quantity_per_bundle", "total_quantity"):
        values = dict(quantity_per_bundle=1, total_quantity=2)
        values[column] = quantity
        with rejected(pg):
            insert(pg, "draft_components", id=uuid4(), draft_item_id=item, component_product_id=product,
                   sku_snapshot="COMPONENT", title_snapshot="Component", base_unit_price_minor=10000, **values)


@pytest.mark.postgres
def test_line_total_and_saved_state_checks(pg):
    product, _, draft, _ = draft_line(pg)
    for unit, total in ((10000, 1), (0, 0), (-1, -1), (9223372036854775807, 9223372036854775807)):
        with rejected(pg):
            insert(pg, "draft_items", id=uuid4(), draft_id=draft, position=1, product_id=product,
                   sku_snapshot="OTHER", title_snapshot="Other", quantity=2,
                   unit_price_minor=unit, line_total_minor=total)
    for clause in ("state='paid'", "channel='ozon_marketplace'", "payable_total_minor=0", "goods_total_minor=-1"):
        with rejected(pg):
            pg.execute(text(f"UPDATE checkout_drafts SET {clause} WHERE id=:id"), {"id": draft})


@pytest.mark.postgres
def test_saved_snapshot_survives_catalog_edits_and_blocks_deletion(pg):
    product, _, draft, item = draft_line(pg)
    insert(pg, "site_prices", product_id=product, amount_minor=10000, currency="RUB")
    pg.execute(text("UPDATE products SET title='Changed', active=false, version=version+1 WHERE id=:id"), {"id": product})
    pg.execute(text("UPDATE site_prices SET amount_minor=50000, version=version+1 WHERE product_id=:id"), {"id": product})
    row = pg.execute(text("SELECT title_snapshot,unit_price_minor,line_total_minor FROM draft_items WHERE id=:id"), {"id": item}).one()
    assert tuple(row) == ("Frozen title", 10000, 20000)
    assert pg.scalar(text("SELECT state FROM checkout_drafts WHERE id=:id"), {"id": draft}) == "saved"
    pg.execute(text("DELETE FROM site_prices WHERE product_id=:id"), {"id": product})
    with rejected(pg):
        pg.execute(text("DELETE FROM products WHERE id=:id"), {"id": product})


@pytest.mark.postgres
def test_bundle_pointer_must_belong_to_same_product(pg):
    product, _, _ = setup_cart(pg)
    other, _, _ = setup_cart(pg)
    version = uuid4()
    insert(pg, "bundle_versions", id=version, product_id=product, number=1)
    with rejected(pg):
        pg.execute(text("UPDATE products SET current_bundle_version_id=:version WHERE id=:product"), {"version": version, "product": other})


@pytest.mark.postgres
def test_deferred_idempotency_can_be_completed_in_same_transaction(pg):
    _, guest, cart = setup_cart(pg)
    draft, quote = uuid4(), uuid4()
    insert(pg, "idempotency_records", id=uuid4(), principal_id=guest, operation="create_checkout_draft", key_hash="preallocated", request_hash="hash", draft_id=draft, response_status=201)
    insert(pg, "draft_quotes", id=quote, guest_session_id=guest, cart_id=cart, cart_version=1, state="valid", currency="RUB", goods_total_minor=1, expires_at=datetime.now(timezone.utc) + timedelta(minutes=15), snapshot_json='{}', catalog_signature="hash")
    insert(pg, "checkout_drafts", id=draft, guest_session_id=guest, quote_id=quote, state="saved", channel="site", currency="RUB", goods_total_minor=1, contact_snapshot='{}', address_snapshot='{}')
    # Force the same deferred validation used at commit while leaving test data rolled back.
    pg.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    _, foreign, _ = setup_cart(pg)
    with rejected(pg):
        insert(pg, "idempotency_records", id=uuid4(), principal_id=foreign, operation="create_checkout_draft", key_hash="foreign", request_hash="hash", draft_id=draft, response_status=201)


@pytest.mark.postgres
def test_direct_empty_upgrade_matches_model_schema(pg_engine):
    """A missing migration/model table, type, unique or FK fails real inspection."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from elton_database.models.catalog import Base
    from elton_database.models import guest, drafts
    engine, _ = pg_engine
    schema = "test_foundation_empty_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.connect() as conn:
            conn.execute(text(f'SET search_path TO "{schema}"'))
            conn.commit()
            command.upgrade(config(conn), "head")
            conn.commit()
            migration_context = MigrationContext.configure(conn)
            assert compare_metadata(migration_context, Base.metadata) == []
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.postgres
def test_seed_is_repeatable_and_repository_loads_sorted_catalog(pg):
    spec = importlib.util.spec_from_file_location("seed_demo", ROOT / "scripts/seed_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from elton_database.models.catalog import Product
    from elton_database.repositories.catalog import CatalogRepository
    with Session(bind=pg, join_transaction_mode="create_savepoint") as session:
        module.seed_demo(session, DB / "fixtures/catalog.synthetic.json")
        module.seed_demo(session, DB / "fixtures/catalog.synthetic.json")
        ids = list(session.scalars(select(Product.id)))
        rows = CatalogRepository(session).load_products(ids[::-1], for_update=True)
        assert [row.id for row in rows] == sorted(ids)
        assert len(rows) == 3
        assert session.scalar(text("SELECT count(*) FROM categories")) == 5
        assert session.scalar(text("SELECT count(*) FROM bundle_components")) == 2
        assert session.scalar(text("SELECT count(*) FROM guest_sessions")) == 0
