"""Stage 1 fail-closed checks for deferred commerce capabilities.

These tests deliberately exercise the public API boundary only.  There is no
provider test double here: a passing result means that the foundation does not
expose a command which could create a commercial fact or make an external
call.  Provider contract tests belong to the later Ozon integration task.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from elton_api.capabilities import CapabilitiesDTO
from elton_api.config import Settings
from elton_api.main import create_app


DEFERRED_COMMANDS = (
    ("POST", "/api/v1/orders"),
    ("POST", "/api/v1/orders/00000000-0000-0000-0000-000000000001/payment-attempts"),
    ("POST", "/api/v1/orders/00000000-0000-0000-0000-000000000001/delivery"),
    ("POST", "/api/v1/auth/sms/challenges"),
    ("POST", "/api/v1/auth/sms/verify"),
    ("POST", "/api/v1/admin/returns/00000000-0000-0000-0000-000000000001/refund-requests"),
    ("POST", "/api/v1/promotions/apply"),
    ("POST", "/api/v1/provider/callbacks/ozon"),
)


def _client(settings_values, unreachable_database_url) -> TestClient:
    settings = Settings(database_url=unreachable_database_url, **settings_values)
    return TestClient(create_app(settings))


def test_capabilities_are_server_owned_and_all_commercial_flags_are_false(
    settings_values, unreachable_database_url
):
    """The browser cannot opt into payment, delivery, SMS, refund or stock."""
    with _client(settings_values, unreachable_database_url) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "foundation_demo"
    for field in (
        "real_checkout",
        "payment",
        "delivery",
        "stock_reservation",
        "sms",
        "customer_account",
        "returns",
        "refunds",
        "reviews",
    ):
        assert payload[field] is False

    # The DTO also rejects an attempted client-side capability escalation.
    assert CapabilitiesDTO.model_validate(payload) == CapabilitiesDTO()
    try:
        CapabilitiesDTO.model_validate({**payload, "payment": True})
    except ValueError:
        pass
    else:  # pragma: no cover - a regression would make the test fail loudly
        raise AssertionError("commercial capability was client-selectable")


def test_deferred_commands_are_unregistered_and_make_no_network_or_local_fact(
    settings_values, unreachable_database_url, monkeypatch
):
    """Deferred commands fail closed before provider or persistence work.

    The unreachable PostgreSQL URL ensures a route cannot silently turn this
    test into a persistence integration test. Since all deferred commands are
    intentionally unregistered in Stage 1, each request must stop at the API
    router with a stable NOT_FOUND problem response. The OpenAPI absence and
    zero response-level facts are the relevant boundary; patching raw sockets
    would also intercept AnyIO's in-process TestClient transport.
    """
    monkeypatch.delenv("OZON_API_KEY", raising=False)
    monkeypatch.delenv("OZON_CLIENT_ID", raising=False)
    monkeypatch.delenv("OZON_SERVER_ID", raising=False)

    with _client(settings_values, unreachable_database_url) as client:
        paths = client.get("/openapi.json").json()["paths"]
        for method, path in DEFERRED_COMMANDS:
            assert path not in paths
            response = client.request(method, path, json={})
            assert response.status_code == 404
            problem = response.json()
            assert problem["code"] == "NOT_FOUND"
            assert problem["status"] == 404
            assert "provider" not in response.text.lower()
            assert "payment" not in response.text.lower()
            assert "refund" not in response.text.lower()


def test_saved_local_draft_contract_contains_no_commercial_facts(
    settings_values, unreachable_database_url
):
    """A local foundation response cannot be mistaken for a paid order.

    This checks the route and OpenAPI contract without inventing a draft in an
    unavailable database.  Actual snapshot/ownership persistence remains an
    explicit PostgreSQL gate in the acceptance report.
    """
    with _client(settings_values, unreachable_database_url) as client:
        schema = client.get("/openapi.json").json()

    draft_save = schema["paths"]["/api/v1/checkout-drafts"]["post"]
    draft_get = schema["paths"]["/api/v1/checkout-drafts/{draft_id}"]["get"]
    for operation in (draft_save, draft_get):
        serialized = str(operation).lower()
        for forbidden in ("payment_id", "provider_id", "reservation", "ledger", "purchase", "refund"):
            assert forbidden not in serialized
