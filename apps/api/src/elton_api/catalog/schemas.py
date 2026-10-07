"""Public catalog contracts; no provider or private commercial fields."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

MAX_MINOR = 9223372036854775807
MAX_QUANTITY = 2147483647


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Money(DTO):
    amount_minor: Annotated[StrictStr, Field(pattern=r"^(0|[1-9][0-9]*)$")]
    currency: Literal["RUB"] = "RUB"

    @field_validator("amount_minor")
    @classmethod
    def bounded(cls, value: str) -> str:
        if len(value) > 19 or int(value) > MAX_MINOR:
            raise ValueError("Money exceeds the bigint boundary")
        return value


class Availability(DTO):
    state: Literal["unknown"] = "unknown"
    quantity: None = None
    source: None = None
    observed_at: None = None


class MediaDTO(DTO):
    id: UUID
    type: Literal["image", "video"]
    url: str
    alt_text: str
    position: int


class CategoryDTO(DTO):
    id: UUID
    slug: str
    title: str


class CategoryPage(DTO):
    items: list[CategoryDTO]


class ProductSummary(DTO):
    id: UUID
    sku: str
    slug: str
    title: str
    type: Literal["single", "bundle"]
    price: Money
    original_price: Money | None = None
    thumbnail: MediaDTO | None = None
    availability: Availability = Field(default_factory=Availability)
    version: int


class BundleComponentDTO(DTO):
    product_id: UUID
    sku: str
    title: str
    quantity: int
    base_unit_price: Money


class BundleDTO(DTO):
    version_id: UUID
    version: int
    components: list[BundleComponentDTO]


class CatalogDelivery(DTO):
    state: Literal["not_connected"] = "not_connected"


class ProductDetail(ProductSummary):
    description: str
    categories: list[CategoryDTO]
    attributes: dict
    seo: dict
    media: list[MediaDTO]
    related_product_ids: list[UUID]
    bundle: BundleDTO | None = None
    delivery: CatalogDelivery = Field(default_factory=CatalogDelivery)


class ProductPage(DTO):
    items: list[ProductSummary]
    next_cursor: str | None = None


class CollectionDTO(DTO):
    id: UUID
    slug: str
    title: str


class CollectionPage(DTO):
    items: list[CollectionDTO]


class CollectionDetail(CollectionDTO):
    items: list[ProductSummary]
