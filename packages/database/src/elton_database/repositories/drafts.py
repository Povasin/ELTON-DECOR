"""Scoped local snapshots; caller owns the single commit, no mutation API."""
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from elton_database.models.drafts import (
    CheckoutDraft, DraftComponent, DraftItem, DraftQuote, IdempotencyRecord,
    checkout_drafts, draft_components, draft_items, draft_quotes, idempotency_records,
)


class DraftRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_quote(self, **values) -> DraftQuote:
        self.session.execute(insert(draft_quotes).values(**values))
        return self.session.get(DraftQuote, values["id"])

    def quote_for_owner(self, quote_id: UUID, owner: UUID) -> DraftQuote | None:
        return self.session.scalar(select(DraftQuote).where(DraftQuote.id == quote_id, DraftQuote.guest_session_id == owner).with_for_update())

    def claim_idempotency(self, owner: UUID, key_hash: str, request_hash: str, draft_id: UUID) -> tuple[IdempotencyRecord, bool]:
        # A conflicting insert waits for the other transaction's durable result.
        # Its preallocated draft FK is deferred; no placeholder can commit alone.
        row_id = uuid4()
        inserted = self.session.scalar(pg_insert(idempotency_records).values(id=row_id, principal_id=owner, operation="create_checkout_draft", key_hash=key_hash, request_hash=request_hash, draft_id=draft_id, response_status=201).on_conflict_do_nothing(constraint="uq_idempotency_scope").returning(idempotency_records.c.id))
        record = self.session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.principal_id == owner, IdempotencyRecord.operation == "create_checkout_draft", IdempotencyRecord.key_hash == key_hash))
        return record, inserted is not None

    def create_draft(self, quote: DraftQuote, draft_id: UUID, contact: dict, address: dict) -> None:
        self.session.execute(insert(checkout_drafts).values(id=draft_id, guest_session_id=quote.guest_session_id, quote_id=quote.id, state="saved", channel="site", currency="RUB", goods_total_minor=quote.goods_total_minor, contact_snapshot=contact, address_snapshot=address))
        for position, line in enumerate(quote.snapshot_json["items"]):
            item_id = uuid4()
            self.session.execute(insert(draft_items).values(id=item_id, draft_id=draft_id, position=position, product_id=UUID(line["product_id"]), sku_snapshot=line["sku"], title_snapshot=line["title"], quantity=line["quantity"], unit_price_minor=int(line["unit_price"]["amount_minor"]), line_total_minor=int(line["line_total"]["amount_minor"]), bundle_version_id=UUID(line["bundle_version_id"]) if line["bundle_version_id"] else None))
            for component in line["components"]:
                self.session.execute(insert(draft_components).values(id=uuid4(), draft_item_id=item_id, component_product_id=UUID(component["product_id"]), sku_snapshot=component["sku"], title_snapshot=component["title"], quantity_per_bundle=component["quantity_per_bundle"], total_quantity=component["total_quantity"], base_unit_price_minor=int(component["base_unit_price"]["amount_minor"])))
        quote.state = "consumed"
        quote.consumed_by_draft_id = draft_id
        self.session.flush()

    def draft_for_owner(self, draft_id: UUID, owner: UUID) -> CheckoutDraft | None:
        return self.session.scalar(select(CheckoutDraft).where(CheckoutDraft.id == draft_id, CheckoutDraft.guest_session_id == owner))

    def saved_items(self, draft_id: UUID) -> list[tuple[DraftItem, list[DraftComponent]]]:
        items = list(self.session.scalars(select(DraftItem).where(DraftItem.draft_id == draft_id).order_by(DraftItem.position)))
        components = list(self.session.scalars(select(DraftComponent).join(DraftItem, DraftComponent.draft_item_id == DraftItem.id).where(DraftItem.draft_id == draft_id).order_by(DraftComponent.component_product_id)))
        return [(item, [c for c in components if c.draft_item_id == item.id]) for item in items]
