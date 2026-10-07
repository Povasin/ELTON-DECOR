"""Frozen draft money behavior; persistence tests require actual PostgreSQL."""
import importlib
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from elton_api.main import create_app
from test_guest_cart import pg_runtime, pg_session, new_guest, protected, PRODUCT, BUNDLE


def task_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("elton_api.drafts"):
            pytest.fail("Task 4 behavior is not implemented", pytrace=False)
        raise


def command(quote_id):
    return {"quote_id": quote_id, "contact": {"phone": "+70000000000", "name": "Demo Guest", "email": "demo@example.invalid"}, "address": {"city": "Demo City", "address_line": "Synthetic Street 1", "postal_code": "000000"}}


def quoted(client, product=BUNDLE, quantity=2):
    csrf = new_guest(client)
    assert client.put(f"/api/v1/cart/items/{product}", json={"quantity": quantity}, headers=protected(csrf)).status_code == 200
    response = client.post("/api/v1/draft-quotes", json={"cart_version": 2}, headers=protected(csrf))
    assert response.status_code == 201, response.text
    return csrf, response.json()


def saved(client, csrf, quote, key=None, payload=None):
    return client.post("/api/v1/checkout-drafts", json=payload or command(quote["quote_id"]), headers=protected(csrf) | {"Idempotency-Key": key or str(uuid4())})


def test_server_snapshot_integer_precision_and_bundle_component_totals():
    service = task_module("elton_api.drafts.quote_service")
    schemas = task_module("elton_api.drafts.schemas")
    components = [{"product_id": PRODUCT, "sku": "DEMO-FLOWER", "title": "Demo flower", "quantity_per_bundle": 1, "total_quantity": 2, "base_unit_price": {"amount_minor": "10000"}}, {"product_id": uuid4(), "sku": "DEMO-VASE", "title": "Demo vase", "quantity_per_bundle": 1, "total_quantity": 2, "base_unit_price": {"amount_minor": "20000"}}]
    line = schemas.DraftLineSnapshot(product_id=BUNDLE, sku="DEMO-BUNDLE", title="Demo bundle", quantity=2, unit_price={"amount_minor": "29000"}, line_total={"amount_minor": "58000"}, bundle_version_id=uuid4(), components=components)
    snapshot = service.checked_snapshot([line])
    assert snapshot["goods_total"]["amount_minor"] == "58000"
    assert snapshot["delivery"] == {"state": "not_connected", "amount": None}
    assert snapshot["payable_total"] is None
    assert [x["total_quantity"] for x in snapshot["items"][0]["components"]] == [2, 2]
    line = schemas.DraftLineSnapshot(product_id=PRODUCT, sku="DEMO", title="Demo", quantity=1, unit_price={"amount_minor": "9007199254740993"}, line_total={"amount_minor": "9007199254740993"})
    assert service.checked_snapshot([line])["goods_total"]["amount_minor"] == "9007199254740993"


@pytest.mark.parametrize("kind", ["line", "aggregate", "component", "mismatch"])
def test_snapshot_refuses_overflow_or_inconsistent_server_arithmetic(kind):
    service = task_module("elton_api.drafts.quote_service")
    schemas = task_module("elton_api.drafts.schemas")
    from fastapi import HTTPException
    line = {"product_id": PRODUCT, "sku": "DEMO", "title": "Demo", "quantity": 1, "unit_price": {"amount_minor": "9223372036854775807"}, "line_total": {"amount_minor": "9223372036854775807"}}
    if kind == "line":
        line["quantity"] = 2
    if kind == "component":
        line["quantity"] = 2
        line["unit_price"] = {"amount_minor": "1"}
        line["line_total"] = {"amount_minor": "2"}
        line["components"] = [{"product_id": uuid4(), "sku": "COMP", "title": "Demo", "quantity_per_bundle": 2147483647, "total_quantity": 1, "base_unit_price": {"amount_minor": "1"}}]
    if kind == "mismatch":
        line["line_total"] = {"amount_minor": "1"}
    lines = [schemas.DraftLineSnapshot(**line)]
    if kind == "aggregate":
        lines += [schemas.DraftLineSnapshot(product_id=uuid4(), sku="OTHER", title="Demo", quantity=1, unit_price={"amount_minor": "1"}, line_total={"amount_minor": "1"})]
    with pytest.raises(HTTPException) as exc:
        service.checked_snapshot(lines)
    assert exc.value.status_code == 422


@pytest.mark.postgres
def test_bundle_money_and_saved_snapshot_survive_catalog_edits(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        assert quote["goods_total"]["amount_minor"] == "58000"
        assert [c["total_quantity"] for c in quote["items"][0]["components"]] == [2, 2]
        assert quote["items"][0]["components"][0]["base_unit_price"]["amount_minor"] == "10000"
        response = saved(client, csrf, quote)
        assert response.status_code == 201
        result = response.json()
        assert result["goods_total"]["amount_minor"] == "58000"
        assert result["delivery"]["amount"] is None and result["payable_total"] is None
        assert result["state"] == "saved" and result["channel"] == "site"
        assert result["message"] == "Заявка сохранена; оплата и доставка пока не подключены"
        with pg_session(pg_runtime) as session:
            new_bom = uuid4()
            session.execute(text("INSERT INTO bundle_versions(id,product_id,number) VALUES(:id,:product,2)"), {"id": new_bom, "product": BUNDLE})
            session.execute(text("INSERT INTO bundle_components(version_id,component_product_id,quantity) VALUES(:id,:product,3)"), {"id": new_bom, "product": PRODUCT})
            session.execute(text("UPDATE products SET current_bundle_version_id=:id WHERE id=:product"), {"id": new_bom, "product": BUNDLE})
            session.execute(text("UPDATE products SET title='Changed',active=false,version=version+1"))
            session.execute(text("UPDATE site_prices SET amount_minor=amount_minor+1,version=version+1"))
        assert client.get(f'/api/v1/checkout-drafts/{result["id"]}').json() == result
        assert result["items"][0]["bundle_version_id"] == "30000000-0000-4000-8000-000000000001"
        assert [c["total_quantity"] for c in result["items"][0]["components"]] == [2, 2]
        for forbidden in ("payment", "fulfillment", "reservation", "ledger", "provider_id", "purchase"):
            assert forbidden not in result


@pytest.mark.postgres
def test_saved_and_retrieved_draft_preserves_integer_string_precision(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=9007199254740993 WHERE product_id=:id"), {"id": PRODUCT})
        csrf, quote = quoted(client, PRODUCT, 1)
        response = saved(client, csrf, quote)
        assert response.status_code == 201
        result = response.json()
        assert result["goods_total"]["amount_minor"] == "9007199254740993"
        assert result["items"][0]["unit_price"]["amount_minor"] == "9007199254740993"
        assert result["items"][0]["line_total"]["amount_minor"] == "9007199254740993"
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=1,version=version+1 WHERE product_id=:id"), {"id": PRODUCT})
        retrieved = client.get(f'/api/v1/checkout-drafts/{result["id"]}')
        assert retrieved.status_code == 200
        assert retrieved.json() == result
        assert retrieved.json()["goods_total"]["amount_minor"] == "9007199254740993"


@pytest.mark.postgres
def test_pg_precision_and_quote_overflow_refusal(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=9007199254740993 WHERE product_id=:id"), {"id": PRODUCT})
        csrf, quote = quoted(client, PRODUCT, 1)
        assert quote["goods_total"]["amount_minor"] == "9007199254740993"
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=9223372036854775807 WHERE product_id=:id"), {"id": PRODUCT})
            session.execute(text("UPDATE cart_items SET quantity=2 WHERE product_id=:id"), {"id": PRODUCT})
        rejected = client.post("/api/v1/draft-quotes", json={"cart_version": 2}, headers=protected(csrf))
        assert rejected.status_code == 422
        with pg_session(pg_runtime) as session:
            assert session.scalar(text("SELECT count(*) FROM draft_quotes")) == 1
