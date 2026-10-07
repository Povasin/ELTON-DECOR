"""Persistent guest cart. All reads and writes scope by server principal."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from elton_database.models.guest import Cart, CartItem, cart_items


class CartRepository:
    def __init__(self, session: Session):
        self.session = session

    def for_owner(self, guest_id: UUID, *, for_update: bool = False) -> Cart | None:
        statement = select(Cart).where(Cart.guest_session_id == guest_id)
        if for_update:
            statement = statement.with_for_update()
        else:
            statement = statement.with_for_update(read=True)
        return self.session.scalar(statement)

    def items(self, cart_id: UUID) -> list[CartItem]:
        return list(self.session.scalars(select(CartItem).where(CartItem.cart_id == cart_id).order_by(CartItem.product_id)))

    def set_quantity(self, cart: Cart, product_id: UUID, quantity: int) -> None:
        self.session.execute(insert(cart_items).values(cart_id=cart.id, product_id=product_id, quantity=quantity).on_conflict_do_update(index_elements=[cart_items.c.cart_id, cart_items.c.product_id], set_={"quantity": quantity}))
        cart.version += 1
        cart.updated_at = datetime.now(timezone.utc)
        self.session.flush()

    def delete_item(self, cart: Cart, product_id: UUID) -> None:
        result = self.session.execute(delete(cart_items).where(cart_items.c.cart_id == cart.id, cart_items.c.product_id == product_id))
        if result.rowcount:
            cart.version += 1
            cart.updated_at = datetime.now(timezone.utc)
            self.session.flush()
