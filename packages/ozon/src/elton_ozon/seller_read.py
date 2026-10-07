"""Fixed-path, server-side read client for a limited Seller API contract.

The supported paths are deliberately enumerated here instead of being supplied
by callers.  This keeps an adapter configuration error from turning into an
SSRF primitive or an accidental mutation client.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from random import random
from time import sleep
from typing import Any, Callable, Generic, TypeVar

import httpx


SELLER_ORIGIN = "https://api-seller.ozon.ru"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_PAGE_SIZE = 1000
_REVIEW_MIN_PAGE_SIZE = 20
_REVIEW_MAX_PAGE_SIZE = 100
_MAX_ATTEMPTS = 3
_MAX_RETRY_DELAY_SECONDS = 30.0
_BASE_RETRY_DELAY_SECONDS = 0.25

T = TypeVar("T")


class OzonReadError(RuntimeError):
    """A safe, credential-free error for callers of the read adapter."""


class OzonConfigurationError(OzonReadError):
    """Raised when required server-side credentials are absent."""


class OzonTransportError(OzonReadError):
    """Raised for a connection or timeout failure before a response arrives."""


class OzonContractError(OzonReadError):
    """Raised when a response cannot satisfy the recorded contract."""


class OzonProviderError(OzonReadError):
    """Non-success response without retaining provider payload or secrets."""

    def __init__(self, status_code: int, retry_after_seconds: int | None = None) -> None:
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Ozon Seller read request failed with HTTP {status_code}")


@dataclass(frozen=True)
class SellerCredentials:
    """Runtime-only Seller credentials; never serialize or log this object."""

    client_id: str = field(repr=False)
    api_key: str = field(repr=False)

    def validate(self) -> None:
        if not self.client_id.strip() or not self.api_key.strip():
            raise OzonConfigurationError("Ozon Seller credentials are required")


@dataclass(frozen=True)
class Page(Generic[T]):
    """A provider page with an opaque continuation token."""

    items: tuple[T, ...]
    cursor: str | None
    has_next: bool | None = None


def _positive_limit(limit: int, *, minimum: int = 1, maximum: int = _MAX_PAGE_SIZE) -> int:
    if not minimum <= limit <= maximum:
        raise ValueError(f"limit must be between {minimum} and {maximum}")
    return limit


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = int(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _object(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OzonContractError(f"Seller response field {field} must be an object")
    return value


def _items(result: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    value = result.get("items", [])
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise OzonContractError("Seller response result.items must be an array of objects")
    return tuple(dict(item) for item in value)


class OzonSellerReadClient:
    """Read-only Seller API subset recorded in the 2026-10-07 contract spike.

    `transport` exists solely to make synthetic contract fixtures testable. It
    does not let callers replace the fixed HTTPS Ozon origin.
    """

    _PATHS = {
        "products": "/v3/product/list",
        "product_info": "/v3/product/info/list",
        "stocks": "/v4/product/info/stocks",
        "reviews": "/v2/review/list",
    }

    def __init__(
        self,
        credentials: SellerCredentials,
        *,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = _MAX_ATTEMPTS,
        sleep: Callable[[float], None] = sleep,
        random_unit: Callable[[], float] = random,
    ) -> None:
        credentials.validate()
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._random_unit = random_unit
        self._client = httpx.Client(
            base_url=SELLER_ORIGIN,
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "Client-Id": credentials.client_id,
                "Api-Key": credentials.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OzonSellerReadClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def list_products(self, *, limit: int = 1000, last_id: str = "") -> Page[Mapping[str, Any]]:
        """Read seller product mappings; cursor is opaque and must be replayed verbatim."""
        result = self._post(
            "products",
            {"filter": {"visibility": "ALL"}, "last_id": last_id, "limit": _positive_limit(limit)},
        )
        cursor = result.get("last_id")
        if not isinstance(cursor, str):
            raise OzonContractError("Seller response result.last_id must be a string")
        return Page(items=_items(result), cursor=cursor or None)

    def product_info(
        self,
        *,
        offer_ids: tuple[str, ...] = (),
        product_ids: tuple[int, ...] = (),
        skus: tuple[int, ...] = (),
    ) -> tuple[Mapping[str, Any], ...]:
        """Bulk-enrich a single identifier family without importing it anywhere."""
        supplied = sum(bool(group) for group in (offer_ids, product_ids, skus))
        if supplied != 1:
            raise ValueError("provide exactly one of offer_ids, product_ids, or skus")
        identifiers: dict[str, Any]
        if offer_ids:
            identifiers = {"offer_id": list(offer_ids)}
        elif product_ids:
            identifiers = {"product_id": list(product_ids)}
        else:
            identifiers = {"sku": list(skus)}
        count = len(next(iter(identifiers.values())))
        _positive_limit(count)
        result = self._post("product_info", {"product_id": [], "offer_id": [], "sku": [], **identifiers})
        return _items(result)

    def stock_snapshot(
        self,
        *,
        cursor: str = "",
        limit: int = 1000,
        visibility: str = "ALL",
    ) -> Page[Mapping[str, Any]]:
        """Read raw stock observations; it never asserts website availability."""
        if not visibility:
            raise ValueError("visibility is required")
        result = self._post(
            "stocks",
            {"cursor": cursor, "filter": {"visibility": visibility}, "limit": _positive_limit(limit)},
        )
        next_cursor = result.get("cursor")
        if not isinstance(next_cursor, str):
            raise OzonContractError("Seller response result.cursor must be a string")
        total_items = result.get("total_items")
        if total_items is not None and not isinstance(total_items, int):
            raise OzonContractError("Seller response result.total_items must be an integer")
        return Page(items=_items(result), cursor=next_cursor or None)

    def list_reviews(
        self,
        *,
        last_id: str = "",
        limit: int = _REVIEW_MIN_PAGE_SIZE,
        status: str = "ALL",
        sort_dir: str = "DESC",
    ) -> Page[Mapping[str, Any]]:
        """Read review metadata only; publication entitlement remains outside this client."""
        if not status or sort_dir not in {"ASC", "DESC"}:
            raise ValueError("status and sort_dir must be valid")
        result = self._post(
            "reviews",
            {
                "filter": {"status": status},
                "last_id": last_id,
                "limit": _positive_limit(limit, minimum=_REVIEW_MIN_PAGE_SIZE, maximum=_REVIEW_MAX_PAGE_SIZE),
                "sort_dir": sort_dir,
            },
        )
        next_last_id = result.get("last_id")
        has_next = result.get("has_next")
        if not isinstance(next_last_id, str) or not isinstance(has_next, bool):
            raise OzonContractError("Seller review response must include last_id and has_next")
        reviews = result.get("reviews", [])
        if not isinstance(reviews, list) or not all(isinstance(item, Mapping) for item in reviews):
            raise OzonContractError("Seller response reviews must be an array of objects")
        return Page(items=tuple(dict(item) for item in reviews), cursor=next_last_id or None, has_next=has_next)

    def _post(self, operation: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        path = self._PATHS[operation]
        for attempt in range(self._max_attempts):
            try:
                response = self._client.post(path, json=payload)
            except httpx.HTTPError as error:
                if attempt + 1 == self._max_attempts:
                    raise OzonTransportError("Ozon Seller read request could not be completed") from error
                self._sleep(self._retry_delay(attempt, retry_after_seconds=None))
                continue
            retry_after_seconds = _retry_after(response)
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt + 1 == self._max_attempts:
                    raise OzonProviderError(response.status_code, retry_after_seconds)
                self._sleep(self._retry_delay(attempt, retry_after_seconds=retry_after_seconds))
                continue
            if response.is_error:
                raise OzonProviderError(response.status_code, retry_after_seconds)
            break
        else:  # pragma: no cover - the loop either returns, breaks, or raises.
            raise OzonTransportError("Ozon Seller read request could not be completed")
        try:
            payload = response.json()
        except ValueError as error:
            raise OzonContractError("Seller response is not valid JSON") from error
        root = _object(payload, field="root")
        return _object(root.get("result"), field="result")

    def _retry_delay(self, attempt: int, *, retry_after_seconds: int | None) -> float:
        if retry_after_seconds is not None:
            return min(float(retry_after_seconds), _MAX_RETRY_DELAY_SECONDS)
        cap = min(_BASE_RETRY_DELAY_SECONDS * (2**attempt), _MAX_RETRY_DELAY_SECONDS)
        return cap * min(1.0, max(0.0, self._random_unit()))
