"""Atomic local saves and replay before all mutable quote guards."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from elton_api.drafts.quote_service import QuoteService
from elton_api.drafts.schemas import DraftDTO, DraftSaveCommand, request_hash
from elton_database.repositories.cart import CartRepository
from elton_database.repositories.drafts import DraftRepository


@dataclass(frozen=True)
class SavedDraftResult:
    dto: DraftDTO
    replayed: bool


class SaveService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = DraftRepository(session)

    def get_draft(self, principal, draft_id: UUID) -> DraftDTO:
        draft = self.repository.draft_for_owner(draft_id, principal.id)
        if draft is None:
            raise HTTPException(404, detail="NOT_FOUND")
        lines = []
        for item, components in self.repository.saved_items(draft.id):
            lines.append({"product_id": item.product_id, "sku": item.sku_snapshot, "title": item.title_snapshot, "quantity": item.quantity, "unit_price": {"amount_minor": str(item.unit_price_minor)}, "line_total": {"amount_minor": str(item.line_total_minor)}, "bundle_version_id": item.bundle_version_id, "components": [{"product_id": c.component_product_id, "sku": c.sku_snapshot, "title": c.title_snapshot, "quantity_per_bundle": c.quantity_per_bundle, "total_quantity": c.total_quantity, "base_unit_price": {"amount_minor": str(c.base_unit_price_minor)}} for c in components]})
        return DraftDTO(id=draft.id, created_at=draft.created_at, items=lines, goods_total={"amount_minor": str(draft.goods_total_minor)}, contact=draft.contact_snapshot, address=draft.address_snapshot)

    def save_draft(self, principal, command: DraftSaveCommand, idempotency_key: str) -> SavedDraftResult:
        draft_id = uuid4()
        body_hash = request_hash(command)
        record, inserted = self.repository.claim_idempotency(principal.id, hashlib.sha256(idempotency_key.encode()).hexdigest(), body_hash, draft_id)
        if not inserted:
            if record.request_hash != body_hash:
                raise HTTPException(409, detail="IDEMPOTENCY_CONFLICT")
            return SavedDraftResult(self.get_draft(principal, record.draft_id), True)
        cart = CartRepository(self.session).for_owner(principal.id, for_update=True)
        quote = self.repository.quote_for_owner(command.quote_id, principal.id)
        if quote is None or cart is None or quote.cart_id != cart.id:
            raise HTTPException(404, detail="NOT_FOUND")
        if quote.state != "valid" or quote.consumed_by_draft_id is not None:
            raise HTTPException(409, detail="QUOTE_USED")
        if quote.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(410, detail="QUOTE_EXPIRED")
        if cart.version != quote.cart_version:
            raise HTTPException(409, detail="CART_CHANGED")
        _, signature = QuoteService(self.session).catalog_snapshot(cart, changed_code="QUOTE_CHANGED")
        # Catalog locks may have waited past the deadline. The new save must
        # still be valid after the complete snapshot has been acquired.
        if quote.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(410, detail="QUOTE_EXPIRED")
        if signature != quote.catalog_signature:
            raise HTTPException(409, detail="QUOTE_CHANGED")
        self.repository.create_draft(quote, draft_id, command.contact.model_dump(mode="json"), command.address.model_dump(mode="json"))
        return SavedDraftResult(self.get_draft(principal, draft_id), False)
