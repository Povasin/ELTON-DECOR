"""Admin DTOs with an intentionally narrow stage-1 command surface."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, SecretStr, StrictStr, field_validator, model_validator

from elton_api.catalog.schemas import DTO, MAX_MINOR, MAX_QUANTITY, MediaDTO, Money


class ProductWriteDTO(DTO):
    title: StrictStr | None = Field(default=None, min_length=1, max_length=300)
    description: StrictStr | None = Field(default=None, max_length=10000)
    active: bool | None = None
    attributes: dict | None = None
    seo: dict | None = None
    related_product_ids: list[UUID] | None = None

    @field_validator("attributes", "seo")
    @classmethod
    def reject_reserved_keys(cls, value):
        reserved = {
            "paid", "delivered", "fbo", "provider", "provider_id", "provider_state",
            "payment", "payment_id", "payment_status", "fulfillment", "fulfillment_id",
            "fulfillment_status", "stock", "stock_id", "reservation", "reservation_id",
            "ledger", "ledger_id", "purchase", "purchase_id", "refund", "refund_id",
            "delivery", "delivery_id", "order", "order_id", "external_id",
        }

        def walk(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in reserved or any(normalized.endswith("_" + suffix) for suffix in reserved if "_" not in suffix):
                        raise ValueError("reserved catalog field")
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(value)
        return value


class ProductCreateDTO(DTO):
    """The one command that can assign a SKU.

    SKU is deliberately absent from ProductWriteDTO: once a row exists it is
    an immutable catalog identity and cannot be changed through PATCH.
    """

    sku: StrictStr = Field(min_length=1, max_length=120)
    title: StrictStr = Field(min_length=1, max_length=300)
    description: StrictStr = Field(default="", max_length=10000)
    type: Literal["single", "bundle"] = "single"
    slug: StrictStr | None = Field(default=None, min_length=1, max_length=300)
    active: bool = True
    attributes: dict | None = None
    seo: dict | None = None
    related_product_ids: list[UUID] = Field(default_factory=list, max_length=100)
    category_ids: list[UUID] = Field(default_factory=list, max_length=50)
    price: Money
    original_price: Money | None = None

    @field_validator("sku", "title")
    @classmethod
    def trim_text(cls, value):
        result = value.strip()
        if not result:
            raise ValueError("text must not be blank")
        return result

    @field_validator("description", "slug")
    @classmethod
    def trim_optional_text(cls, value):
        return value.strip() if value is not None else value

    @field_validator("attributes", "seo")
    @classmethod
    def reject_reserved_keys(cls, value):
        # Keep the same trust boundary as product PATCH.  Importing the
        # validator through a base class would make the API schema harder to
        # read and would hide the reserved-field rule from OpenAPI users.
        reserved = {
            "paid", "delivered", "fbo", "provider", "provider_id", "provider_state",
            "payment", "payment_id", "payment_status", "fulfillment", "fulfillment_id",
            "fulfillment_status", "stock", "stock_id", "reservation", "reservation_id",
            "ledger", "ledger_id", "purchase", "purchase_id", "refund", "refund_id",
            "delivery", "delivery_id", "order", "order_id", "external_id",
        }

        def walk(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    normalized = str(key).strip().lower().replace("-", "_")
                    if normalized in reserved or any(normalized.endswith("_" + suffix) for suffix in reserved if "_" not in suffix):
                        raise ValueError("reserved catalog field")
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(value)
        return value

    @field_validator("related_product_ids")
    @classmethod
    def unique_related(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("duplicate related product")
        return value

    @field_validator("price")
    @classmethod
    def require_positive_price(cls, value: Money) -> Money:
        if int(value.amount_minor) <= 0:
            raise ValueError("site price must be positive")
        return value

    @field_validator("original_price")
    @classmethod
    def require_valid_original_price(cls, value: Money | None) -> Money | None:
        if value is not None and int(value.amount_minor) <= 0:
            raise ValueError("original price must be positive")
        return value

    @model_validator(mode="after")
    def original_not_below_current(self):
        if self.original_price is not None and int(self.original_price.amount_minor) < int(self.price.amount_minor):
            raise ValueError("original price must not be below current price")
        return self


class SitePriceWriteDTO(DTO):
    price: Money
    original_price: Money | None = None

    @field_validator("price")
    @classmethod
    def require_positive_price(cls, value: Money) -> Money:
        if int(value.amount_minor) <= 0:
            raise ValueError("site price must be positive")
        return value

    @field_validator("original_price")
    @classmethod
    def require_valid_original_price(cls, value: Money | None) -> Money | None:
        if value is not None and int(value.amount_minor) <= 0:
            raise ValueError("original price must be positive")
        return value

    @model_validator(mode="after")
    def original_not_below_current(self):
        if self.original_price is not None and int(self.original_price.amount_minor) < int(self.price.amount_minor):
            raise ValueError("original price must not be below current price")
        return self


class BundleComponentInput(DTO):
    product_id: UUID
    quantity: Annotated[int, Field(strict=True, ge=1, le=MAX_QUANTITY)]


class BundleWriteDTO(DTO):
    components: list[BundleComponentInput] = Field(min_length=1, max_length=100)

    @field_validator("components")
    @classmethod
    def unique_components(cls, value: list[BundleComponentInput]) -> list[BundleComponentInput]:
        ids = [x.product_id for x in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate bundle component")
        return value


class BundleAdminComponentDTO(DTO):
    product_id: UUID
    sku: str
    title: str
    quantity: int
    base_unit_price: Money


class BundleAdminDTO(DTO):
    version_id: UUID
    version: int
    components: list[BundleAdminComponentDTO]


class ProductAdminDTO(DTO):
    id: UUID
    sku: str
    slug: str
    type: Literal["single", "bundle"]
    title: str
    description: str
    active: bool
    attributes: dict
    seo: dict
    version: int
    price: Money | None = None
    original_price: Money | None = None
    related_product_ids: list[UUID] = Field(default_factory=list)
    # Detail-only fields are optional so the existing collection response stays
    # wire-compatible while GET /products/{id} can power the editor in one call.
    media: list[MediaDTO] = Field(default_factory=list)
    bundle: BundleAdminDTO | None = None


class ProductAdminPageDTO(DTO):
    items: list[ProductAdminDTO]
    next_cursor: str | None = None


class AdminProductListQuery(DTO):
    q: StrictStr = Field(default="", max_length=300)
    limit: int = Field(default=50, ge=1, le=100)
    cursor: StrictStr | None = Field(default=None, max_length=512)


class AdminDraftDTO(DTO):
    id: UUID
    state: Literal["saved"]
    channel: Literal["site"]
    created_at: datetime
    goods_total: Money
    contact: dict
    address: dict


class DraftPageDTO(DTO):
    items: list[AdminDraftDTO]
    next_cursor: str | None = None


class DraftListQuery(DTO):
    cursor: str | None = Field(default=None, max_length=512)
    created_from: datetime | None = None
    created_to: datetime | None = None


class AdminLoginDTO(DTO):
    email: StrictStr = Field(min_length=3, max_length=254)
    password: SecretStr

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("invalid email")
        return normalized

    @field_validator("password")
    @classmethod
    def bounded_password(cls, value: SecretStr) -> SecretStr:
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("invalid password")
        return value


class AdminSessionDTO(DTO):
    id: UUID
    email: str
    permissions: list[str]
    csrf_token: str
    expires_at: datetime
