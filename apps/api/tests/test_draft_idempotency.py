"""Atomic retry and catalog/cart races, using actual PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from elton_api.main import create_app
from test_guest_cart import pg_runtime, pg_session, protected, PRODUCT, BUNDLE
from test_draft_money import command, quoted, saved, task_module


@pytest.mark.parametrize("section,field", [("contact", "phone"), ("contact", "name"), ("contact", "email"), ("address", "city"), ("address", "address_line"), ("address", "postal_code")])
def test_all_normalized_contact_address_fields_affect_hash(section, field):
    schemas = task_module("elton_api.drafts.schemas")
    payload = command(str(uuid4()))
    original = schemas.DraftSaveCommand.model_validate(payload)
    payload[section][field] = "  Changed   demo  "
    changed = schemas.DraftSaveCommand.model_validate(payload)
    assert changed.model_dump()[section][field] == "Changed demo"
    assert schemas.request_hash(original) != schemas.request_hash(changed)


def test_normalization_equates_whitespace_omitted_and_blank_optionals():
    schemas = task_module("elton_api.drafts.schemas")
    quote_id = str(uuid4())
    a = {"quote_id": quote_id, "contact": {"phone": "  +70000000000  ", "name": " \t ", "email": None}, "address": {"city": "  Demo\n City ", "address_line": "Street   1", "postal_code": " "}}
    b = {"quote_id": quote_id, "contact": {"phone": "+70000000000"}, "address": {"city": "Demo City", "address_line": "Street 1"}}
    assert schemas.request_hash(schemas.DraftSaveCommand.model_validate(a)) == schemas.request_hash(schemas.DraftSaveCommand.model_validate(b))
    b["quote_id"] = str(uuid4())
    assert schemas.request_hash(schemas.DraftSaveCommand.model_validate(a)) != schemas.request_hash(schemas.DraftSaveCommand.model_validate(b))


@pytest.mark.postgres
def test_replay_after_expiry_cart_and_catalog_change_and_hash_conflict(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        key = str(uuid4())
        first = saved(client, csrf, quote, key)
        assert first.status_code == 201
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE draft_quotes SET expires_at=:past"), {"past": datetime.now(timezone.utc) - timedelta(minutes=1)})
            session.execute(text("UPDATE products SET title='Changed',version=version+1"))
            session.execute(text("UPDATE carts SET version=version+1"))
        replay = saved(client, csrf, quote, key)
        assert replay.status_code == 201 and replay.json() == first.json()
        assert replay.headers["Idempotency-Replayed"] == "true"
        changed = command(quote["quote_id"])
        changed["contact"]["name"] = "Other Demo"
        conflict = saved(client, csrf, quote, key, changed)
        assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
        used = saved(client, csrf, quote)
        assert used.status_code == 409 and used.json()["code"] == "QUOTE_USED"
        with pg_session(pg_runtime) as session:
            assert session.scalar(text("SELECT count(*) FROM checkout_drafts")) == 1
            assert session.scalar(text("SELECT count(*) FROM idempotency_records")) == 1


@pytest.mark.postgres
@pytest.mark.parametrize("change,code,status", [("expiry", "QUOTE_EXPIRED", 410), ("cart", "CART_CHANGED", 409), ("price", "QUOTE_CHANGED", 409), ("title", "QUOTE_CHANGED", 409), ("activity", "QUOTE_CHANGED", 409), ("component_price", "QUOTE_CHANGED", 409), ("component_activity", "QUOTE_CHANGED", 409), ("component_title", "QUOTE_CHANGED", 409), ("bom", "QUOTE_CHANGED", 409)])
def test_pre_save_changes_reject_without_draft_or_idempotency(pg_runtime, change, code, status):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        with pg_session(pg_runtime) as session:
            if change == "expiry":
                session.execute(text("UPDATE draft_quotes SET expires_at=:past"), {"past": datetime.now(timezone.utc) - timedelta(seconds=1)})
            elif change == "cart":
                session.execute(text("UPDATE carts SET version=version+1"))
            elif change == "bom":
                bom = uuid4()
                session.execute(text("INSERT INTO bundle_versions(id,product_id,number) VALUES(:id,:product,2)"), {"id": bom, "product": BUNDLE})
                session.execute(text("INSERT INTO bundle_components(version_id,component_product_id,quantity) VALUES(:id,:product,2)"), {"id": bom, "product": PRODUCT})
                session.execute(text("UPDATE products SET current_bundle_version_id=:id,version=version+1 WHERE id=:product"), {"id": bom, "product": BUNDLE})
            else:
                product = PRODUCT if change.startswith("component_") else BUNDLE
                mutation = "UPDATE site_prices SET amount_minor=amount_minor+1,version=version+1" if "price" in change else "UPDATE products SET active=false,version=version+1" if "activity" in change else "UPDATE products SET title='Changed',version=version+1"
                session.execute(text(mutation + " WHERE " + ("product_id" if "price" in change else "id") + "=:id"), {"id": product})
        response = saved(client, csrf, quote)
        assert response.status_code == status and response.json()["code"] == code
        with pg_session(pg_runtime) as session:
            assert session.scalar(text("SELECT count(*) FROM checkout_drafts")) == 0
            assert session.scalar(text("SELECT count(*) FROM idempotency_records")) == 0
            assert session.scalar(text("SELECT state FROM draft_quotes")) == "valid"


@pytest.mark.postgres
def test_failed_commit_rolls_back_every_write_and_same_key_can_retry(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        key = str(uuid4())
        def fail_commit(session):
            raise OperationalError("synthetic pre-commit failure", None, Exception("synthetic"))
        event.listen(Session, "before_commit", fail_commit)
        try:
            failed = saved(client, csrf, quote, key)
        finally:
            event.remove(Session, "before_commit", fail_commit)
        assert failed.status_code == 503
        with pg_session(pg_runtime) as session:
            for table in ("checkout_drafts", "draft_items", "draft_components", "idempotency_records"):
                assert session.scalar(text(f"SELECT count(*) FROM {table}")) == 0
            assert session.scalar(text("SELECT state FROM draft_quotes")) == "valid"
        assert saved(client, csrf, quote, key).status_code == 201


@pytest.mark.postgres
def test_pre_save_aggregate_overflow_is_catalog_conflict(pg_runtime):
    from uuid import UUID
    vase = UUID("20000000-0000-4000-8000-000000000002")
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, _ = quoted(client, PRODUCT, 1)
        assert client.put(f"/api/v1/cart/items/{vase}", json={"quantity": 1}, headers=protected(csrf, '"2"')).status_code == 200
        quote_response = client.post("/api/v1/draft-quotes", json={"cart_version": 3}, headers=protected(csrf))
        assert quote_response.status_code == 201
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE site_prices SET amount_minor=9223372036854775807,version=version+1 WHERE product_id IN (:a,:b)"), {"a": PRODUCT, "b": vase})
        response = saved(client, csrf, quote_response.json())
        assert response.status_code == 409 and response.json()["code"] == "QUOTE_CHANGED"


@pytest.mark.postgres
def test_concurrent_lost_response_retries_create_one_draft(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        proof = client.cookies.get("elton_guest")
    key, barrier = str(uuid4()), Barrier(2)
    def save(_):
        with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
            client.cookies.set("elton_guest", proof, path="/api")
            barrier.wait(timeout=10)
            response = saved(client, csrf, quote, key)
            assert response.status_code == 201
            return response.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    assert results[0] == results[1]
    # Treat the first successful response as lost; a fresh app recovers it.
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        client.cookies.set("elton_guest", proof, path="/api")
        assert saved(client, csrf, quote, key).json() == results[0]
    with pg_session(pg_runtime) as session:
        assert session.scalar(text("SELECT count(*) FROM checkout_drafts")) == 1


def wait_for_db_blocker(runtime, blocking_pid, table):
    """Observe a real query waiting on this transaction, not an HTTP start."""
    with runtime[1].connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        deadline = monotonic() + 10
        while monotonic() < deadline:
            observer.execute(text("SELECT pg_stat_clear_snapshot()"))
            waiting_pid = observer.scalar(text("SELECT pid FROM pg_stat_activity WHERE :blocker = ANY(pg_blocking_pids(pid)) AND wait_event_type='Lock' AND query ILIKE :query"), {"blocker": blocking_pid, "query": f"%FROM {table}%"})
            if waiting_pid is not None:
                return waiting_pid
            sleep(0.02)
    pytest.fail(f"No PostgreSQL {table} query waited on the expected transaction")


def mutate_locked_catalog_or_cart(writer, race):
    if race == "catalog":
        writer.execute(text("SELECT id FROM products ORDER BY id FOR UPDATE")).all()
        writer.execute(text("UPDATE site_prices SET amount_minor=amount_minor+1,version=version+1"))
        writer.execute(text("UPDATE products SET title='Race title',version=version+1"))
        bom = uuid4()
        writer.execute(text("INSERT INTO bundle_versions(id,product_id,number) VALUES(:id,:product,2)"), {"id": bom, "product": BUNDLE})
        writer.execute(text("INSERT INTO bundle_components(version_id,component_product_id,quantity) VALUES(:id,:product,3)"), {"id": bom, "product": PRODUCT})
        writer.execute(text("UPDATE products SET current_bundle_version_id=:id WHERE id=:product"), {"id": bom, "product": BUNDLE})
    else:
        writer.execute(text("SELECT id FROM carts FOR UPDATE")).all()
        writer.execute(text("UPDATE carts SET version=version+1"))


@pytest.mark.postgres
@pytest.mark.parametrize("race", ["catalog", "cart"])
def test_writer_first_save_observably_waits_and_rejects_committed_change(pg_runtime, race):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        proof = client.cookies.get("elton_guest")
    def save():
        with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
            client.cookies.set("elton_guest", proof, path="/api")
            return saved(client, csrf, quote)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg_session(pg_runtime) as writer:
            mutate_locked_catalog_or_cart(writer, race)
            writer_pid = writer.scalar(text("SELECT pg_backend_pid()"))
            future = pool.submit(save)
            wait_for_db_blocker(pg_runtime, writer_pid, "products" if race == "catalog" else "carts")
            assert not future.done()
        response = future.result(timeout=20)
    assert response.status_code == 409
    assert response.json()["code"] == ("QUOTE_CHANGED" if race == "catalog" else "CART_CHANGED")
    with pg_session(pg_runtime) as session:
        assert session.scalar(text("SELECT count(*) FROM checkout_drafts")) == 0


@pytest.mark.postgres
@pytest.mark.parametrize("race", ["catalog", "cart"])
def test_save_first_blocks_writer_until_complete_old_snapshot_is_committed(pg_runtime, race):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        proof = client.cookies.get("elton_guest")
    snapshot_written, release_save = Event(), Event()
    saving_pid = []
    def pause_after_real_draft_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO checkout_drafts"):
            saving_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            snapshot_written.set()
            assert release_save.wait(timeout=15), "Test did not release the saving transaction"
    def save():
        with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
            client.cookies.set("elton_guest", proof, path="/api")
            return saved(client, csrf, quote)
    def write():
        with pg_session(pg_runtime) as writer:
            mutate_locked_catalog_or_cart(writer, race)
    event.listen(Engine, "after_cursor_execute", pause_after_real_draft_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            save_future = pool.submit(save)
            try:
                assert snapshot_written.wait(timeout=10)
                writer_future = pool.submit(write)
                wait_for_db_blocker(pg_runtime, saving_pid[0], "products" if race == "catalog" else "carts")
                assert not writer_future.done()
            finally:
                release_save.set()
            response = save_future.result(timeout=20)
            writer_future.result(timeout=20)
    finally:
        event.remove(Engine, "after_cursor_execute", pause_after_real_draft_insert)
    assert response.status_code == 201
    result = response.json()
    assert result["items"] == quote["items"]
    assert result["goods_total"] == {"amount_minor": "58000", "currency": "RUB"}
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as reader:
        reader.cookies.set("elton_guest", proof, path="/api")
        assert reader.get(f'/api/v1/checkout-drafts/{result["id"]}').json() == result


@pytest.mark.postgres
def test_quote_expires_while_save_is_blocked_on_actual_catalog_lock(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        proof = client.cookies.get("elton_guest")
    with pg_session(pg_runtime) as session:
        expires = session.scalar(text("UPDATE draft_quotes SET expires_at=clock_timestamp()+interval '5 seconds' WHERE id=:id RETURNING expires_at"), {"id": UUID(quote["quote_id"])})
    def save():
        with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
            client.cookies.set("elton_guest", proof, path="/api")
            return saved(client, csrf, quote)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg_session(pg_runtime) as writer:
            writer.execute(text("SELECT id FROM products ORDER BY id FOR UPDATE")).all()
            writer_pid = writer.scalar(text("SELECT pg_backend_pid()"))
            future = pool.submit(save)
            wait_for_db_blocker(pg_runtime, writer_pid, "products")
            assert not future.done()
            # Time elapses in real PG while the catalog remains locked. No
            # production clock, repository or snapshot behavior is mocked.
            writer.execute(text("SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM (CAST(:expires AS timestamptz)-clock_timestamp()))))"), {"expires": expires})
            assert writer.scalar(text("SELECT clock_timestamp() >= :expires"), {"expires": expires})
        response = future.result(timeout=20)
    assert response.status_code == 410 and response.json()["code"] == "QUOTE_EXPIRED"
    with pg_session(pg_runtime) as session:
        assert session.scalar(text("SELECT count(*) FROM checkout_drafts")) == 0
        assert session.scalar(text("SELECT count(*) FROM idempotency_records")) == 0
        assert session.scalar(text("SELECT state FROM draft_quotes")) == "valid"
