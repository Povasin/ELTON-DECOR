"""Server-only, read-only Ozon Seller contract client.

The package intentionally has no FastAPI routes, database code, import worker,
or browser-facing configuration.  It is a narrow adapter boundary only.
"""

from .seller_read import (
    OzonConfigurationError,
    OzonContractError,
    OzonProviderError,
    OzonReadError,
    OzonSellerReadClient,
    OzonTransportError,
    Page,
    SellerCredentials,
)

__all__ = [
    "OzonConfigurationError",
    "OzonContractError",
    "OzonProviderError",
    "OzonReadError",
    "OzonSellerReadClient",
    "OzonTransportError",
    "Page",
    "SellerCredentials",
]
