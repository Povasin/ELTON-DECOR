"""Consistent server catalog snapshots, with integer arithmetic and PG locks."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from elton_api.catalog.schemas import MAX_MINOR, MAX_QUANTITY, Money
from elton_api.drafts.schemas import DraftLineSnapshot, DraftQuoteDTO, SnapshotDTO
from elton_database.models.catalog import BundleComponent, BundleVersion, Product, SitePrice
from elton_database.repositories.cart import CartRepository
from elton_database.repositories.drafts import DraftRepository


def checked_snapshot(lines: list[DraftLineSnapshot]) -> dict:
    total = 0
    for line in lines:
        amount = int(line.unit_price.amount_minor) * line.quantity
        total += amount
        if amount <= 0 or total > MAX_MINOR or amount != int(line.line_total.amount_minor):
            raise HTTPException(422, detail="VALIDATION_ERROR")
        for component in line.components:
            quantity = line.quantity * component.quantity_per_bundle
            if quantity > MAX_QUANTITY or quantity != component.total_quantity or int(component.base_unit_price.amount_minor) <= 0:
                raise HTTPException(422, detail="VALIDATION_ERROR")
    if not lines:
        raise HTTPException(422, detail="VALIDATION_ERROR")
    return SnapshotDTO(items=lines, goods_total=Money(amount_minor=str(total))).model_dump(mode="json")


class QuoteService:
    def __init__(self, session: Session, ttl_seconds: int = 900):
        self.session = session
        self.ttl_seconds = ttl_seconds
        self.carts = CartRepository(session)
        self.drafts = DraftRepository(session)

    def catalog_snapshot(self, cart, *, changed_code: str = "VALIDATION_ERROR") -> tuple[dict, str]:
        def reject():
            raise HTTPException(409 if changed_code == "QUOTE_CHANGED" else 422, detail=changed_code)

        items = self.carts.items(cart.id)
        ids = {item.product_id for item in items}
        # Discover the current immutable BOM, then lock the entire product set in
        # one UUID order. A pointer changed during discovery is rejected below.
        pointers = dict(self.session.execute(select(Product.id, Product.current_bundle_version_id).where(Product.id.in_(ids))).all())
        bom_ids = {value for value in pointers.values() if value is not None}
        discovered = list(self.session.scalars(select(BundleComponent).where(BundleComponent.version_id.in_(bom_ids)).order_by(BundleComponent.version_id, BundleComponent.component_product_id)))
        ids.update(component.component_product_id for component in discovered)
        products = {p.id: p for p in self.session.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id).with_for_update(read=True).execution_options(populate_existing=True))}
        for item in items:
            product = products.get(item.product_id)
            if not product or product.current_bundle_version_id != pointers.get(item.product_id):
                reject()
        prices = {p.product_id: p for p in self.session.scalars(select(SitePrice).where(SitePrice.product_id.in_(ids)).order_by(SitePrice.product_id).with_for_update(read=True).execution_options(populate_existing=True))}
        versions = {v.id: v for v in self.session.scalars(select(BundleVersion).where(BundleVersion.id.in_(bom_ids)).order_by(BundleVersion.id).with_for_update(read=True))}
        components = list(self.session.scalars(select(BundleComponent).where(BundleComponent.version_id.in_(bom_ids)).order_by(BundleComponent.version_id, BundleComponent.component_product_id).with_for_update(read=True).execution_options(populate_existing=True)))
        signature_rows = []
        for product_id in sorted(ids):
            p, price = products.get(product_id), prices.get(product_id)
            if not p or not p.active or not price or not 0 < price.amount_minor <= MAX_MINOR or price.currency != "RUB":
                reject()
            signature_rows.append({"id": str(p.id), "sku": p.sku, "title": p.title, "type": p.type, "active": p.active, "version": p.version, "bom": str(p.current_bundle_version_id) if p.current_bundle_version_id else None, "price": price.amount_minor, "price_version": price.version, "currency": price.currency})
        signature_bom = []
        lines = []
        for item in items:
            p, price = products[item.product_id], prices[item.product_id]
            nested = []
            if p.type == "bundle":
                version = versions.get(p.current_bundle_version_id)
                bom = [c for c in components if c.version_id == p.current_bundle_version_id]
                if not version or version.product_id != p.id or not bom:
                    reject()
                signature_bom.append({"id": str(version.id), "product_id": str(p.id), "number": version.number, "components": [{"id": str(c.component_product_id), "quantity": c.quantity} for c in bom]})
                for c in bom:
                    cp, base = products.get(c.component_product_id), prices.get(c.component_product_id)
                    if not cp or not base or cp.type != "single":
                        reject()
                    quantity = c.quantity * item.quantity
                    if quantity > MAX_QUANTITY:
                        raise HTTPException(409 if changed_code == "QUOTE_CHANGED" else 422, detail=changed_code)
                    nested.append({"product_id": cp.id, "sku": cp.sku, "title": cp.title, "quantity_per_bundle": c.quantity, "total_quantity": quantity, "base_unit_price": {"amount_minor": str(base.amount_minor)}})
            amount = price.amount_minor * item.quantity
            if amount > MAX_MINOR:
                reject()
            lines.append(DraftLineSnapshot(product_id=p.id, sku=p.sku, title=p.title, quantity=item.quantity, unit_price=Money(amount_minor=str(price.amount_minor)), line_total=Money(amount_minor=str(amount)), bundle_version_id=p.current_bundle_version_id if p.type == "bundle" else None, components=nested))
        try:
            snapshot = checked_snapshot(lines)
        except HTTPException:
            if changed_code == "QUOTE_CHANGED":
                reject()
            raise
        signature = hashlib.sha256(json.dumps({"products": signature_rows, "bom": signature_bom}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        return snapshot, signature

    def create_quote(self, principal, cart_version: int) -> DraftQuoteDTO:
        cart = self.carts.for_owner(principal.id, for_update=True)
        if cart is None:
            raise HTTPException(404, detail="NOT_FOUND")
        if cart.version != cart_version:
            raise HTTPException(409, detail="CART_CHANGED")
        snapshot, signature = self.catalog_snapshot(cart)
        quote = self.drafts.create_quote(id=uuid4(), guest_session_id=principal.id, cart_id=cart.id, cart_version=cart.version, state="valid", currency="RUB", goods_total_minor=int(snapshot["goods_total"]["amount_minor"]), expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds), snapshot_json=snapshot, catalog_signature=signature)
        return DraftQuoteDTO(quote_id=quote.id, cart_version=quote.cart_version, expires_at=quote.expires_at, **snapshot)
