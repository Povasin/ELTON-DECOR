from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from elton_ozon import (  # noqa: E402
    OzonConfigurationError,
    OzonContractError,
    OzonProviderError,
    OzonSellerReadClient,
    SellerCredentials,
)


def client(handler):
    return OzonSellerReadClient(
        SellerCredentials(client_id="synthetic-client", api_key="synthetic-key"),
        transport=httpx.MockTransport(handler),
    )


def request_json(request: httpx.Request):
    return json.loads(request.content.decode("utf-8"))


def test_product_page_uses_fixed_seller_path_headers_and_opaque_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api-seller.ozon.ru/v3/product/list")
        assert request.headers["Client-Id"] == "synthetic-client"
        assert request.headers["Api-Key"] == "synthetic-key"
        assert request_json(request) == {
            "filter": {"visibility": "ALL"},
            "last_id": "opaque-before",
            "limit": 2,
        }
        return httpx.Response(200, json={"result": {"items": [{"product_id": 5}], "last_id": "opaque-next"}})

    page = client(handler).list_products(limit=2, last_id="opaque-before")

    assert page.items == ({"product_id": 5},)
    assert page.cursor == "opaque-next"


def test_product_info_allows_exactly_one_identifier_family():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"result": {"items": [{"offer_id": "demo"}]}})

    result = client(handler).product_info(offer_ids=("demo",))

    assert result == ({"offer_id": "demo"},)
    assert calls[0].url.path == "/v3/product/info/list"
    with pytest.raises(ValueError, match="exactly one"):
        client(handler).product_info(offer_ids=("demo",), skus=(1,))


def test_stock_cursor_is_preserved_without_claiming_availability():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v4/product/info/stocks"
        assert request_json(request)["cursor"] == "provider-cursor"
        return httpx.Response(200, json={"result": {"items": [{"present": 7, "reserved": 2}], "cursor": "next"}})

    page = client(handler).stock_snapshot(cursor="provider-cursor", limit=3)

    assert page.items[0] == {"present": 7, "reserved": 2}
    assert page.cursor == "next"


def test_review_response_requires_pagination_contract_but_does_not_publish():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/review/list"
        return httpx.Response(200, json={"result": {"reviews": [{"review_id": "synthetic"}], "last_id": "next", "has_next": True}})

    page = client(handler).list_reviews(limit=20)

    assert page.cursor == "next"
    assert page.has_next is True
    assert page.items == ({"review_id": "synthetic"},)


def test_provider_errors_are_safe_and_preserve_retry_after_only():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "12"}, json={"message": "secret provider detail"})

    with pytest.raises(OzonProviderError) as raised:
        OzonSellerReadClient(
            SellerCredentials(client_id="synthetic-client", api_key="synthetic-key"),
            transport=httpx.MockTransport(handler),
            max_attempts=1,
        ).list_products()

    assert raised.value.status_code == 429
    assert raised.value.retry_after_seconds == 12
    assert "secret provider detail" not in str(raised.value)


def test_invalid_or_missing_contract_is_rejected():
    with pytest.raises(OzonConfigurationError):
        OzonSellerReadClient(SellerCredentials(client_id="", api_key="x"))

    with pytest.raises(OzonContractError):
        client(lambda _: httpx.Response(200, json={"result": {"items": "not-a-list", "last_id": ""}})).list_products()


def test_credentials_never_include_secret_values_in_repr():
    credentials = SellerCredentials(client_id="synthetic-client", api_key="synthetic-secret")

    rendered = repr(credentials)

    assert "synthetic-client" not in rendered
    assert "synthetic-secret" not in rendered


def test_retries_429_with_capped_retry_after_and_no_jitter():
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "999"})
        return httpx.Response(200, json={"result": {"items": [], "last_id": ""}})

    result = OzonSellerReadClient(
        SellerCredentials(client_id="synthetic-client", api_key="synthetic-key"),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        random_unit=lambda: 0.0,
    ).list_products()

    assert result.items == ()
    assert attempts == 2
    assert sleeps == [30.0]


def test_retries_transport_failure_with_exponential_jitter():
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("synthetic failure")
        return httpx.Response(200, json={"result": {"items": [], "last_id": ""}})

    OzonSellerReadClient(
        SellerCredentials(client_id="synthetic-client", api_key="synthetic-key"),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        random_unit=lambda: 1.0,
    ).list_products()

    assert attempts == 2
    assert sleeps == [0.25]


def test_retries_5xx_with_bounded_exponential_jitter():
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"result": {"items": [], "last_id": ""}})

    OzonSellerReadClient(
        SellerCredentials(client_id="synthetic-client", api_key="synthetic-key"),
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        random_unit=lambda: 1.0,
    ).list_products()

    assert attempts == 2
    assert sleeps == [0.25]


def test_does_not_retry_ordinary_client_error():
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(403, json={"message": "do not retry"})

    with pytest.raises(OzonProviderError) as raised:
        client(handler).list_products()

    assert raised.value.status_code == 403
    assert attempts == 1


@pytest.mark.parametrize("limit", [0, 1001])
def test_product_page_rejects_unbounded_pagination(limit: int):
    with pytest.raises(ValueError):
        client(lambda _: pytest.fail("HTTP must not be called")).list_products(limit=limit)
