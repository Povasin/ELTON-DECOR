"""Local immutable quote/draft contracts and canonical contact normalization."""
from datetime import datetime
import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictStr, field_validator

from elton_api.catalog.schemas import DTO, MAX_MINOR, MAX_QUANTITY, Money
from elton_api.cart.schemas import CartDelivery

Quantity = Annotated[int, Field(strict=True, ge=1, le=MAX_QUANTITY)]


class NormalizedFields(DTO):
    @field_validator("*", mode="before")
    @classmethod
    def normalize(cls, value):
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value


class ContactDemo(NormalizedFields):
    phone: Annotated[StrictStr, Field(min_length=1, max_length=32)]
    name: Annotated[StrictStr, Field(max_length=120)] | None = None
    email: Annotated[StrictStr, Field(max_length=254)] | None = None


class AddressDemo(NormalizedFields):
    city: Annotated[StrictStr, Field(min_length=1, max_length=120)]
    address_line: Annotated[StrictStr, Field(min_length=1, max_length=500)]
    postal_code: Annotated[StrictStr, Field(max_length=20)] | None = None


class DraftSaveCommand(DTO):
    quote_id: UUID
    contact: ContactDemo
    address: AddressDemo


def request_hash(command: DraftSaveCommand) -> str:
    canonical = json.dumps(command.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class QuoteCommand(DTO):
    cart_version: Annotated[int, Field(strict=True, ge=1, le=MAX_MINOR)]


class DraftComponentSnapshot(DTO):
    product_id: UUID
    sku: str
    title: str
    quantity_per_bundle: Quantity
    total_quantity: Quantity
    base_unit_price: Money


class DraftLineSnapshot(DTO):
    product_id: UUID
    sku: str
    title: str
    quantity: Quantity
    unit_price: Money
    line_total: Money
    bundle_version_id: UUID | None = None
    components: list[DraftComponentSnapshot] = Field(default_factory=list)


class QuoteCapabilities(DTO):
    save_draft: Literal[True] = True
    pay: Literal[False] = False
    submit_delivery: Literal[False] = False


class DraftCapabilities(DTO):
    pay: Literal[False] = False
    cancel: Literal[False] = False
    return_: Literal[False] = Field(default=False, alias="return")
    submit_delivery: Literal[False] = False


class SnapshotDTO(DTO):
    items: list[DraftLineSnapshot]
    goods_total: Money
    delivery: CartDelivery = Field(default_factory=CartDelivery)
    payable_total: None = None


class DraftQuoteDTO(SnapshotDTO):
    quote_id: UUID
    cart_version: int
    state: Literal["valid"] = "valid"
    expires_at: datetime
    capabilities: QuoteCapabilities = Field(default_factory=QuoteCapabilities)


class DraftDTO(SnapshotDTO):
    id: UUID
    state: Literal["saved"] = "saved"
    channel: Literal["site"] = "site"
    created_at: datetime
    contact: ContactDemo
    address: AddressDemo
    capabilities: DraftCapabilities = Field(default_factory=DraftCapabilities)
    message: Literal["Заявка сохранена; оплата и доставка пока не подключены"] = "Заявка сохранена; оплата и доставка пока не подключены"
