from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictInt
from elton_api.catalog.schemas import DTO, MAX_QUANTITY, Money


class QuantityCommand(DTO):
    quantity: Annotated[StrictInt, Field(ge=1, le=MAX_QUANTITY)]


class CartLine(DTO):
    product_id: UUID
    quantity: int
    unit_price: Money | None
    line_total: Money | None
    issue: Literal["PRODUCT_INACTIVE", "PRICE_MISSING", "BUNDLE_INVALID", "CALCULATION_OVERFLOW"] | None


class CartDelivery(DTO):
    state: Literal["not_connected"] = "not_connected"
    amount: None = None


class CartDTO(DTO):
    id: UUID
    version: int
    items: list[CartLine]
    goods_total: Money | None
    can_quote: bool
    delivery: CartDelivery = Field(default_factory=CartDelivery)
    payable_total: None = None
