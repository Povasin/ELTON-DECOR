"""Guest trust scope and persistent cart, independent of customer/admin auth."""
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from .catalog import Base, pk, quantity_check, timestamp, version

guest_sessions = Table("guest_sessions", Base.metadata, pk(),
    Column("token_hash", String, nullable=False, unique=True), timestamp("created_at"),
    Column("expires_at", DateTime(timezone=True), nullable=False), Column("revoked_at", DateTime(timezone=True)))
carts = Table("carts", Base.metadata, pk(),
    Column("guest_session_id", UUID(as_uuid=True), ForeignKey("guest_sessions.id", ondelete="RESTRICT"), nullable=False, unique=True),
    version(), timestamp("updated_at"), UniqueConstraint("id", "guest_session_id", name="uq_cart_owner"),
    CheckConstraint("version > 0", name="ck_cart_version"))
cart_items = Table("cart_items", Base.metadata,
    Column("cart_id", UUID(as_uuid=True), ForeignKey("carts.id", ondelete="RESTRICT"), primary_key=True),
    Column("product_id", UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True),
    Column("quantity", Integer, nullable=False), quantity_check("quantity", "ck_cart_item_quantity"))


class GuestSession(Base):
    __table__ = guest_sessions


class Cart(Base):
    __table__ = carts


class CartItem(Base):
    __table__ = cart_items
