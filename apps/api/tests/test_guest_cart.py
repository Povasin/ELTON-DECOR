"""Task 3 behavior. Persistence evidence uses actual PostgreSQL only."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from elton_api.config import Settings
from elton_api.main import create_app

ROOT = Path(__file__).resolve().parents[3]
PRODUCT = UUID("20000000-0000-4000-8000-000000000001")
BUNDLE = UUID("20000000-0000-4000-8000-000000000003")
ORIGIN = {"Origin": "http://localhost:3000"}


def task_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("elton_api"):
            pytest.fail("Task 3 behavior is not implemented", pytrace=False)
        raise


@pytest.fixture
def offline_client(settings_values, unreachable_database_url):
    with TestClient(create_app(Settings(database_url=unreachable_database_url, **settings_values))) as client:
        yield client


def test_missing_guest_proof_denies_cart_without_pg(offline_client):
    response = offline_client.get("/api/v1/cart")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"
    assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("origin", [None, "http://localhost:3001", "http://localhost:3000/", "https://foreign.example"])
def test_guest_creation_requires_exact_origin_before_storage(offline_client, origin):
    response = offline_client.post("/api/v1/guest-sessions", headers={} if origin is None else {"Origin": origin})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_storage_failure_is_private_retryable_problem(offline_client):
    response = offline_client.post("/api/v1/guest-sessions", headers=ORIGIN)
    assert response.status_code == 503
    assert response.headers["Content-Type"].startswith("application/problem+json")
    assert response.json()["code"] == "STORAGE_TEMPORARILY_UNAVAILABLE"
    assert response.json()["retryable"] is True
    assert response.headers["X-Request-ID"] == response.json()["trace_id"]
    assert "synthetic" not in response.text


def test_server_integer_money_and_quantity_calculation():
    service = task_module("elton_api.cart.service")
    line = service.PricedCartLine(PRODUCT, 2, 10000)
    cart = service.calculate_cart(uuid4(), 1, [line]).model_dump(mode="json")
    assert cart["items"][0]["unit_price"] == {"amount_minor": "10000", "currency": "RUB"}
    assert cart["items"][0]["line_total"]["amount_minor"] == "20000"
    assert cart["goods_total"]["amount_minor"] == "20000"
    assert cart["can_quote"] is True
    assert cart["delivery"] == {"state": "not_connected", "amount": None}
    assert cart["payable_total"] is None


@pytest.mark.parametrize("changes,issue", [
    ({"active": False}, "PRODUCT_INACTIVE"),
    ({"amount_minor": None}, "PRICE_MISSING"),
    ({"bundle_valid": False}, "BUNDLE_INVALID"),
])
def test_invalid_lines_stay_visible_and_prevent_partial_total(changes, issue):
    service = task_module("elton_api.cart.service")
    args = dict(product_id=PRODUCT, quantity=2, amount_minor=10000)
    args.update(changes)
    cart = service.calculate_cart(uuid4(), 1, [service.PricedCartLine(**args), service.PricedCartLine(uuid4(), 1, 900)]).model_dump(mode="json")
    assert len(cart["items"]) == 2
    assert cart["items"][0]["issue"] == issue
    assert cart["items"][0]["line_total"] is None
    assert cart["goods_total"] is None
    assert cart["can_quote"] is False


def test_empty_cart_cannot_quote():
    service = task_module("elton_api.cart.service")
    cart = service.calculate_cart(uuid4(), 1, [])
    assert cart.goods_total.amount_minor == "0"
    assert cart.can_quote is False


@pytest.mark.parametrize("lines", [[(2, 9223372036854775807)], [(1, 9223372036854775807), (1, 1)]])
def test_bigint_overflow_is_rejected_before_writing(lines):
    service = task_module("elton_api.cart.service")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        service.calculate_cart(uuid4(), 1, [service.PricedCartLine(uuid4(), q, amount) for q, amount in lines])
    assert exc.value.status_code == 422


@pytest.mark.parametrize("payload", [{"quantity": 0}, {"quantity": -1}, {"quantity": 2147483648}, {"quantity": 1.0}, {"quantity": True}, {"quantity": 2, "price": {"amount_minor": "1", "currency": "RUB"}}])
def test_cart_command_rejects_client_prices_and_non_integer_quantities(payload):
    module = task_module("elton_api.cart.schemas")
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        module.QuantityCommand.model_validate(payload)


def test_csrf_is_bound_to_session_and_runtime_key():
    csrf = task_module("elton_api.guest.csrf")
    a, b = uuid4(), uuid4()
    import secrets
    key = secrets.token_urlsafe(32)
    token = csrf.csrf_token(a, key)
    assert csrf.valid_csrf(token, a, key)
    assert not csrf.valid_csrf(token, b, key)
    assert not csrf.valid_csrf(token, a, secrets.token_urlsafe(32))
    assert not csrf.valid_csrf(None, a, key)


def test_malformed_csrf_fails_closed():
    csrf = task_module("elton_api.guest.csrf")
    import secrets
    assert not csrf.valid_csrf("é", uuid4(), secrets.token_urlsafe(32))


def test_bundle_component_quantity_overflow_is_rejected():
    service = task_module("elton_api.cart.service")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        service.calculate_cart(uuid4(), 1, [service.PricedCartLine(BUNDLE, 2147483647, 1, component_quantities=(2,))])
    assert exc.value.status_code == 422


def test_pre_session_rate_limit_stops_before_storage(settings_values, unreachable_database_url):
    settings = Settings(database_url=unreachable_database_url, guest_creation_limit_per_minute=1, **settings_values)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/guest-sessions", headers=ORIGIN).status_code == 503
        response = client.post("/api/v1/guest-sessions", headers=ORIGIN)
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.json()["code"] == "RATE_LIMITED"


@pytest.fixture
def pg_runtime(postgres_url, settings_values):
    """Isolated schema in explicitly supplied synthetic PG; never SQLite."""
    engine = create_engine(postgres_url, hide_parameters=True)
    assert engine.dialect.name == "postgresql"
    schema = "test_cart_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()
            cfg = Config(str(ROOT / "packages/database/alembic.ini"))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            connection.commit()
        from sqlalchemy.engine import make_url
        url = make_url(postgres_url).update_query_dict({"options": f"-csearch_path={schema}"})
        runtime_url = url.render_as_string(hide_password=False)
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("seed_task3", ROOT / "scripts/seed_demo.py")
        seed = module_from_spec(spec)
        spec.loader.exec_module(seed)
        with Session(engine) as session:
            session.execute(text(f'SET search_path TO "{schema}"'))
            seed.seed_demo(session, seed.DEFAULT_FIXTURE)
            session.commit()
        yield Settings(database_url=runtime_url, **settings_values), engine, schema
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@contextmanager
def pg_session(runtime):
    _, engine, schema = runtime
    with Session(engine) as session:
        session.execute(text(f'SET search_path TO "{schema}"'))
        yield session
        session.commit()


def new_guest(client):
    response = client.post("/api/v1/guest-sessions", headers=ORIGIN)
    assert response.status_code == 201
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Path=/api" in response.headers["set-cookie"]
    assert "Max-Age=604800" in response.headers["set-cookie"]
    assert response.headers["Cache-Control"] == "private, no-store"
    assert set(response.json()) == {"csrf_token", "expires_at"}
    return response.json()["csrf_token"]


@pytest.mark.postgres
def test_guest_session_replaces_unknown_browser_cookie(pg_runtime):
    """A reset local database must not leave a browser unable to use its cart."""
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        client.cookies.set("elton_guest", "proof-from-a-removed-local-database", domain="localhost.local", path="/api")
        response = client.post("/api/v1/guest-sessions", headers=ORIGIN)
        assert response.status_code == 201
        assert client.cookies.get("elton_guest", domain="localhost.local", path="/api") != "proof-from-a-removed-local-database"
        assert set(response.json()) == {"csrf_token", "expires_at"}


def protected(token, version='"1"'):
    return dict(ORIGIN, **{"X-CSRF-Token": token, "If-Match": version})


@pytest.mark.postgres
def test_two_guest_carts_are_isolated_and_persist_after_app_restart(pg_runtime):
    settings, _, _ = pg_runtime
    with TestClient(create_app(settings), base_url="http://localhost") as a, TestClient(create_app(settings), base_url="http://localhost") as b:
        token_a, token_b = new_guest(a), new_guest(b)
        proof_a, proof_b = a.cookies.get("elton_guest"), b.cookies.get("elton_guest")
        assert proof_a != proof_b
        with pg_session(pg_runtime) as session:
            hashes = session.scalars(text("SELECT token_hash FROM guest_sessions")).all()
            assert proof_a not in hashes and proof_b not in hashes
        cart_a, cart_b = a.get("/api/v1/cart").json(), b.get("/api/v1/cart").json()
        assert cart_a["id"] != cart_b["id"]
        response = a.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 2}, headers=protected(token_a))
        assert response.status_code == 200
        assert response.headers["ETag"] == '"2"'
        assert response.json()["goods_total"]["amount_minor"] == "20000"
        assert b.get("/api/v1/cart").json()["items"] == []
        assert b.get(f'/api/v1/cart/{cart_a["id"]}').status_code == 404
        assert b.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 9}, headers=protected(token_a)).status_code == 403
        assert b.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 1, "price": 1}, headers=protected(token_b)).status_code == 422
        response = a.post("/api/v1/guest-sessions", headers=ORIGIN)
        assert response.status_code == 200 and a.cookies.get("elton_guest") == proof_a
        with TestClient(create_app(settings), base_url="http://localhost") as restarted:
            restarted.cookies.set("elton_guest", proof_a, path="/api")
            assert restarted.get("/api/v1/cart").json()["goods_total"]["amount_minor"] == "20000"
            restarted.cookies.clear()
            restarted.cookies.set("elton_guest", cart_a["id"], path="/api")
            assert restarted.get("/api/v1/cart").status_code == 401


@pytest.mark.postgres
def test_cart_guards_version_noop_delete_and_quantity(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf = new_guest(client)
        for method in (client.put, client.delete):
            kwargs = {"json": {"quantity": 2}} if method == client.put else {}
            assert method(f"/api/v1/cart/items/{PRODUCT}", headers=protected(csrf) | {"Origin": "http://localhost:3001"}, **kwargs).status_code == 403
            assert method(f"/api/v1/cart/items/{PRODUCT}", headers=protected("wrong"), **kwargs).status_code == 403
            assert method(f"/api/v1/cart/items/{PRODUCT}", headers=ORIGIN | {"X-CSRF-Token": csrf}, **kwargs).status_code == 428
        added = client.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 3}, headers=protected(csrf))
        assert added.status_code == 200
        assert added.json()["goods_total"]["amount_minor"] == "30000"
        stale = client.delete(f"/api/v1/cart/items/{PRODUCT}", headers=protected(csrf))
        assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
        noop = client.delete(f"/api/v1/cart/items/{uuid4()}", headers=protected(csrf, '"2"'))
        assert noop.status_code == 200 and noop.headers["ETag"] == '"2"'
        deleted = client.delete(f"/api/v1/cart/items/{PRODUCT}", headers=protected(csrf, '"2"'))
        assert deleted.status_code == 200 and deleted.json()["items"] == []


@pytest.mark.postgres
@pytest.mark.parametrize("guard", ["expired", "revoked"])
def test_expiry_and_revocation_reject_proof_server_side(pg_runtime, guard):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf = new_guest(client)
        with pg_session(pg_runtime) as session:
            column = "expires_at" if guard == "expired" else "revoked_at"
            session.execute(text(f"UPDATE guest_sessions SET {column}=:now"), {"now": datetime.now(timezone.utc) - timedelta(seconds=1)})
        for method, path, kwargs in [(client.get, "/session", {}), (client.get, "/cart", {}), (client.put, f"/cart/items/{PRODUCT}", {"json": {"quantity": 2}, "headers": protected(csrf)})]:
            response = method("/api/v1" + path, **kwargs)
            assert response.status_code == 401


@pytest.mark.postgres
def test_catalog_changes_leave_invalid_cart_lines_visible(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf = new_guest(client)
        assert client.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 2}, headers=protected(csrf)).status_code == 200
        assert client.put(f"/api/v1/cart/items/{BUNDLE}", json={"quantity": 2}, headers=protected(csrf, '"2"')).status_code == 200
        assert client.get("/api/v1/cart").json()["goods_total"]["amount_minor"] == "78000"
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE products SET active=false WHERE id=:id"), {"id": PRODUCT})
        cart = client.get("/api/v1/cart").json()
        assert cart["version"] == 3
        issues = {item["product_id"]: item["issue"] for item in cart["items"]}
        assert issues[str(PRODUCT)] == "PRODUCT_INACTIVE"
        assert issues[str(BUNDLE)] == "BUNDLE_INVALID"
        assert cart["goods_total"] is None and not cart["can_quote"]
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE products SET active=true WHERE id=:id"), {"id": PRODUCT})
            session.execute(text("DELETE FROM site_prices WHERE product_id=:id"), {"id": PRODUCT})
        cart = client.get("/api/v1/cart").json()
        assert next(x for x in cart["items"] if x["product_id"] == str(PRODUCT))["issue"] == "PRICE_MISSING"


@pytest.mark.postgres
def test_concurrent_writes_with_same_version_have_one_winner(pg_runtime):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as owner:
        csrf = new_guest(owner)
        proof = owner.cookies.get("elton_guest")
    barrier = Barrier(2)
    def write(quantity):
        with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
            client.cookies.set("elton_guest", proof, path="/api")
            barrier.wait(timeout=10)
            return client.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": quantity}, headers=protected(csrf)).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [2, 3]))
    assert sorted(results) == [200, 409]
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as reader:
        reader.cookies.set("elton_guest", proof, path="/api")
        cart = reader.get("/api/v1/cart").json()
        assert cart["version"] == 2
        assert len(cart["items"]) == 1


@pytest.mark.postgres
def test_overflow_mutation_rolls_back_item_and_cart_version(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf = new_guest(client)
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=9223372036854775807 WHERE product_id=:id"), {"id": PRODUCT})
        rejected = client.put(f"/api/v1/cart/items/{PRODUCT}", json={"quantity": 2}, headers=protected(csrf))
        assert rejected.status_code == 422 and rejected.json()["code"] == "VALIDATION_ERROR"
        cart = client.get("/api/v1/cart").json()
        assert cart["version"] == 1 and cart["items"] == []


@pytest.mark.parametrize("line", [
    {"quantity": 2, "amount_minor": 9223372036854775807},
    {"quantity": 2147483647, "amount_minor": 1, "component_quantities": (2,)},
])
def test_persisted_overflow_calculations_remain_readable(line):
    service = task_module("elton_api.cart.service")
    # Existing saved quantities can become invalid after price/BOM edits.
    from fastapi import HTTPException
    try:
        cart = service.calculate_cart(uuid4(), 7, [service.PricedCartLine(PRODUCT, **line)], tolerate_overflow=True)
    except (HTTPException, TypeError):
        pytest.fail("Persisted overflow must be rendered as an issue, not rejected", pytrace=False)
    assert cart.items[0].issue == "CALCULATION_OVERFLOW"
    assert cart.items[0].line_total is None
    assert cart.goods_total is None and not cart.can_quote
    assert cart.version == 7


def test_quantity_repair_does_not_require_other_lines_to_be_valid():
    service = task_module("elton_api.cart.service")
    validator = getattr(service, "validate_cart_change", None)
    assert validator is not None, "Cart recovery mutation validator is missing"
    other = uuid4()
    current = [service.PricedCartLine(PRODUCT, 2, 9223372036854775807), service.PricedCartLine(other, 2, 9223372036854775807)]
    prospective = [service.PricedCartLine(PRODUCT, 1, 9223372036854775807), current[1]]
    validator(current, prospective, PRODUCT)
    cart = service.calculate_cart(uuid4(), 2, prospective, tolerate_overflow=True)
    assert cart.items[1].issue == "CALCULATION_OVERFLOW"
    assert cart.goods_total is None and not cart.can_quote


@pytest.mark.parametrize("quantity,existing_amount", [(2, 1), (1, 9223372036854775807)])
def test_recovery_does_not_allow_new_line_or_aggregate_overflow(quantity, existing_amount):
    service = task_module("elton_api.cart.service")
    validator = getattr(service, "validate_cart_change", None)
    assert validator is not None, "Cart recovery mutation validator is missing"
    current = [service.PricedCartLine(uuid4(), 1, existing_amount)]
    prospective = current + [service.PricedCartLine(PRODUCT, quantity, 9223372036854775807)]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        validator(current, prospective, PRODUCT)
    assert exc.value.status_code == 422


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["price", "bom"])
def test_catalog_overflow_keeps_get_delete_and_repair_available(pg_runtime, change):
    vase = UUID("20000000-0000-4000-8000-000000000002")
    affected = PRODUCT if change == "price" else BUNDLE
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf = new_guest(client)
        assert client.put(f"/api/v1/cart/items/{affected}", json={"quantity": 2}, headers=protected(csrf)).status_code == 200
        assert client.put(f"/api/v1/cart/items/{vase}", json={"quantity": 1}, headers=protected(csrf, '"2"')).status_code == 200
        with pg_session(pg_runtime) as session:
            if change == "price":
                session.execute(text("UPDATE site_prices SET amount_minor=9223372036854775807 WHERE product_id=:id"), {"id": PRODUCT})
            else:
                # New immutable BOM, switched as a catalog edit; no frozen BOM update.
                new_bom = uuid4()
                session.execute(text("INSERT INTO bundle_versions(id,product_id,number) VALUES(:id,:product,2)"), {"id": new_bom, "product": BUNDLE})
                session.execute(text("INSERT INTO bundle_components(version_id,component_product_id,quantity) VALUES(:id,:product,2147483647)"), {"id": new_bom, "product": PRODUCT})
                session.execute(text("UPDATE products SET current_bundle_version_id=:id WHERE id=:product"), {"id": new_bom, "product": BUNDLE})
        response = client.get("/api/v1/cart")
        assert response.status_code == 200 and response.headers["ETag"] == '"3"'
        line = next(x for x in response.json()["items"] if x["product_id"] == str(affected))
        assert line["issue"] == "CALCULATION_OVERFLOW" and line["line_total"] is None
        assert response.json()["goods_total"] is None and response.json()["can_quote"] is False
        # An invalid line must not block deletion of a different, valid line.
        unrelated_delete = client.delete(f"/api/v1/cart/items/{vase}", headers=protected(csrf, '"3"'))
        assert unrelated_delete.status_code == 200 and unrelated_delete.headers["ETag"] == '"4"'
        assert len(unrelated_delete.json()["items"]) == 1
        assert unrelated_delete.json()["items"][0]["issue"] == "CALCULATION_OVERFLOW"
        repaired = client.put(f"/api/v1/cart/items/{affected}", json={"quantity": 1}, headers=protected(csrf, '"4"'))
        assert repaired.status_code == 200 and repaired.json()["can_quote"] is True
        # Put the saved quantity back directly to reproduce persisted-invalid recovery.
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE cart_items SET quantity=2 WHERE product_id=:id"), {"id": affected})
        deleted = client.delete(f"/api/v1/cart/items/{affected}", headers=protected(csrf, '"5"'))
        assert deleted.status_code == 200 and deleted.json()["items"] == []
