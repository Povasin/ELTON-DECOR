"""Live guest proof, CSRF and owner-only immutable draft reads."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from elton_api.config import Settings
from elton_api.main import create_app
from test_guest_cart import pg_runtime, pg_session, new_guest, protected
from test_draft_money import command, quoted, saved, task_module


def test_draft_routes_require_session_and_do_not_echo_invalid_pii(settings_values, unreachable_database_url):
    with TestClient(create_app(Settings(database_url=unreachable_database_url, **settings_values))) as client:
        for path, body in [("/api/v1/draft-quotes", {"cart_version": 1}), ("/api/v1/checkout-drafts", command(str(uuid4())))]:
            response = client.post(path, json=body)
            assert response.status_code == 401
            assert response.headers["Cache-Control"] == "private, no-store"
            assert "demo@example.invalid" not in response.text
        assert client.get(f"/api/v1/checkout-drafts/{uuid4()}").status_code == 401


def test_openapi_exposes_idempotency_header_to_generated_clients(settings_values, unreachable_database_url):
    schema = create_app(Settings(database_url=unreachable_database_url, **settings_values)).openapi()
    headers = schema["paths"]["/api/v1/checkout-drafts"]["post"].get("parameters", [])
    assert any(p["in"] == "header" and p["name"] == "Idempotency-Key" for p in headers)


@pytest.mark.parametrize("field", ["price", "stock", "requested_state", "delivery_selection_ref"])
def test_save_command_refuses_untrusted_fields(field):
    schemas = task_module("elton_api.drafts.schemas")
    from pydantic import ValidationError
    payload = command(str(uuid4())) | {field: "synthetic"}
    with pytest.raises(ValidationError):
        schemas.DraftSaveCommand.model_validate(payload)


@pytest.mark.postgres
def test_foreign_unknown_draft_and_quote_are_indistinguishable(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as owner, TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as foreign:
        csrf, quote = quoted(owner)
        result = saved(owner, csrf, quote)
        assert result.status_code == 201
        other_csrf = new_guest(foreign)
        for draft_id in (result.json()["id"], str(uuid4())):
            response = foreign.get(f"/api/v1/checkout-drafts/{draft_id}")
            assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"
            assert "demo@example.invalid" not in response.text
        assert saved(foreign, other_csrf, quote).status_code == 404
        assert owner.get(f'/api/v1/checkout-drafts/{result.json()["id"]}').headers["Cache-Control"] == "private, no-store"


@pytest.mark.postgres
def test_expired_guest_cannot_read_or_replay(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        key = str(uuid4())
        result = saved(client, csrf, quote, key)
        assert result.status_code == 201
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE guest_sessions SET expires_at=:past"), {"past": datetime.now(timezone.utc) - timedelta(seconds=1)})
        for response in (saved(client, csrf, quote, key), client.get(f'/api/v1/checkout-drafts/{result.json()["id"]}')):
            assert response.status_code == 401 and response.json()["code"] == "SESSION_EXPIRED"


@pytest.mark.postgres
def test_quote_save_csrf_and_idempotency_header_guards(pg_runtime):
    with TestClient(create_app(pg_runtime[0]), base_url="http://localhost") as client:
        csrf, quote = quoted(client)
        for headers in (protected("wrong"), protected(csrf) | {"Origin": "http://localhost:3001"}):
            assert client.post("/api/v1/draft-quotes", json={"cart_version": 2}, headers=headers).status_code == 403
            assert client.post("/api/v1/checkout-drafts", json=command(quote["quote_id"]), headers=headers | {"Idempotency-Key": str(uuid4())}).status_code == 403
        assert client.post("/api/v1/checkout-drafts", json=command(quote["quote_id"]), headers=protected(csrf)).status_code == 428
        assert client.post("/api/v1/checkout-drafts", json=command(quote["quote_id"]), headers=protected(csrf) | {"Idempotency-Key": "bad key"}).status_code == 422
