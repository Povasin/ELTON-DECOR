"""Server-only cart prices with checked integer arithmetic."""
from dataclasses import dataclass
import re
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from elton_api.cart.schemas import CartDTO, CartLine
from elton_api.catalog.schemas import MAX_MINOR, MAX_QUANTITY, Money
from elton_api.catalog.service import CatalogService
from elton_database.models.catalog import Product, SitePrice
from elton_database.repositories.cart import CartRepository


@dataclass(frozen=True)
class PricedCartLine:
    product_id: UUID
    quantity: int
    amount_minor: int | None
    active: bool = True
    bundle_valid: bool = True
    component_quantities: tuple[int, ...] = ()


def line_overflows(line: PricedCartLine) -> bool:
    return (
        any(line.quantity * component > MAX_QUANTITY for component in line.component_quantities)
        or (line.amount_minor is not None and line.quantity * line.amount_minor > MAX_MINOR)
    )


def validate_cart_change(current: list[PricedCartLine], prospective: list[PricedCartLine], changed_product_id: UUID) -> None:
    """Reject new overflow while allowing repair with other invalid saved lines."""
    changed = next(line for line in prospective if line.product_id == changed_product_id)
    if line_overflows(changed):
        raise HTTPException(422, detail="VALIDATION_ERROR")
    before = sum(line.quantity * line.amount_minor for line in current if line.amount_minor is not None)
    after = sum(line.quantity * line.amount_minor for line in prospective if line.amount_minor is not None)
    if after > MAX_MINOR and after > before:
        raise HTTPException(422, detail="VALIDATION_ERROR")


def calculate_cart(cart_id: UUID, version: int, lines: list[PricedCartLine], *, tolerate_overflow: bool = False) -> CartDTO:
    items = []
    total = 0
    valid = True
    for line in lines:
        if type(line.quantity) is not int or not 1 <= line.quantity <= MAX_QUANTITY:
            raise HTTPException(422, detail="VALIDATION_ERROR")
        issue = "PRODUCT_INACTIVE" if not line.active else "PRICE_MISSING" if line.amount_minor is None else "BUNDLE_INVALID" if not line.bundle_valid else None
        unit = Money(amount_minor=str(line.amount_minor)) if line.amount_minor is not None else None
        overflow = line_overflows(line)
        if overflow:
            if not tolerate_overflow:
                raise HTTPException(422, detail="VALIDATION_ERROR")
            issue = issue or "CALCULATION_OVERFLOW"
        line_total = None
        if issue:
            valid = False
        else:
            amount = line.quantity * line.amount_minor
            if amount > MAX_MINOR or total + amount > MAX_MINOR:
                if not tolerate_overflow:
                    raise HTTPException(422, detail="VALIDATION_ERROR")
                issue = "CALCULATION_OVERFLOW"
                valid = False
            else:
                total += amount
                line_total = Money(amount_minor=str(amount))
        items.append(CartLine(product_id=line.product_id, quantity=line.quantity, unit_price=unit, line_total=line_total, issue=issue))
    return CartDTO(id=cart_id, version=version, items=items, goods_total=Money(amount_minor=str(total)) if valid else None, can_quote=valid and bool(items))


def expected_version(request: Request) -> int:
    header = request.headers.get("if-match")
    if header is None:
        raise HTTPException(428, detail="PRECONDITION_REQUIRED")
    if not re.fullmatch(r'"[1-9][0-9]{0,18}"', header) or int(header[1:-1]) > MAX_MINOR:
        raise HTTPException(422, detail="VALIDATION_ERROR")
    return int(header[1:-1])


class CartService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = CartRepository(session)

    def priced_line(self, product_id: UUID, quantity: int) -> PricedCartLine:
        catalog = CatalogService(self.session)
        product = self.session.get(Product, product_id)
        price = self.session.get(SitePrice, product_id)
        bundle = catalog.bundle(product) if product and product.type == "bundle" else None
        return PricedCartLine(product_id, quantity, price.amount_minor if price else None, active=bool(product and product.active), bundle_valid=bool(product and (product.type == "single" or bundle)), component_quantities=tuple(x.quantity for x in bundle.components) if bundle else ())

    def render(self, cart) -> CartDTO:
        lines = [self.priced_line(item.product_id, item.quantity) for item in self.repository.items(cart.id)]
        return calculate_cart(cart.id, cart.version, lines, tolerate_overflow=True)

    def get_cart(self, principal) -> CartDTO:
        cart = self.repository.for_owner(principal.id)
        if cart is None:
            raise HTTPException(404, detail="NOT_FOUND")
        return self.render(cart)

    def mutate(self, principal, product_id: UUID, version: int, quantity: int | None) -> CartDTO:
        cart = self.repository.for_owner(principal.id, for_update=True)
        if cart is None:
            raise HTTPException(404, detail="NOT_FOUND")
        if cart.version != version:
            raise HTTPException(409, detail="VERSION_CONFLICT")
        current_items = self.repository.items(cart.id)
        changed = quantity is not None or any(item.product_id == product_id for item in current_items)
        next_version = cart.version + int(changed)
        if next_version > MAX_MINOR:
            raise HTTPException(422, detail="VALIDATION_ERROR")
        prospective = [self.priced_line(item.product_id, item.quantity) for item in current_items if item.product_id != product_id]
        if quantity is not None:
            if self.session.scalar(select(Product.id).where(Product.id == product_id)) is None:
                raise HTTPException(404, detail="NOT_FOUND")
            prospective.append(self.priced_line(product_id, quantity))
        prospective.sort(key=lambda line: line.product_id)
        # Validate the complete proposed aggregate before issuing any write.
        if quantity is not None:
            current = [self.priced_line(item.product_id, item.quantity) for item in current_items]
            validate_cart_change(current, prospective, product_id)
        result = calculate_cart(cart.id, next_version, prospective, tolerate_overflow=True)
        if quantity is None:
            self.repository.delete_item(cart, product_id)
        else:
            self.repository.set_quantity(cart, product_id, quantity)
        return result
