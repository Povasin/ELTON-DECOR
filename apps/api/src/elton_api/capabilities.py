"""Capabilities frozen to the foundation API contract (BR-27)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class CapabilitiesDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["foundation_demo"] = "foundation_demo"
    real_checkout: Literal[False] = False
    payment: Literal[False] = False
    delivery: Literal[False] = False
    stock_reservation: Literal[False] = False
    sms: Literal[False] = False
    customer_account: Literal[False] = False
    returns: Literal[False] = False
    refunds: Literal[False] = False
    reviews: Literal[False] = False
