"""Protected catalog commands and read-only local draft administration."""
from datetime import datetime
import base64
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from elton_api.admin.schemas import BundleAdminDTO, BundleWriteDTO, DraftPageDTO, ProductAdminDTO, ProductAdminPageDTO, ProductCreateDTO, ProductWriteDTO, SitePriceWriteDTO
from elton_api.catalog.service import public_media
from elton_database.models.catalog import BundleComponent, BundleVersion, Product, ProductMedia, SitePrice, bundle_components, bundle_versions, product_categories, product_relations
from elton_database.models.drafts import CheckoutDraft
from elton_database.repositories.admin import AdminRepository


class AdminCatalogService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = AdminRepository(session)

    def _product(self, product_id: UUID, expected_version: int) -> Product:
        product = self.session.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if product is None:
            raise HTTPException(404, detail="NOT_FOUND")
        if product.version != expected_version:
            raise HTTPException(409, detail="VERSION_CONFLICT")
        return product

    def _bundle_dto(self, product: Product) -> BundleAdminDTO | None:
        if product.type != "bundle" or not product.current_bundle_version_id:
            return None
        version = self.session.get(BundleVersion, product.current_bundle_version_id)
        if version is None or version.product_id != product.id:
            return None
        rows = self.session.execute(
            select(BundleComponent, Product, SitePrice)
            .join(Product, Product.id == BundleComponent.component_product_id)
            .join(SitePrice, SitePrice.product_id == Product.id)
            .where(BundleComponent.version_id == version.id)
            .order_by(Product.id)
        ).all()
        return BundleAdminDTO(
            version_id=version.id,
            version=version.number,
            components=[
                {
                    "product_id": component_product.id,
                    "sku": component_product.sku,
                    "title": component_product.title,
                    "quantity": component.quantity,
                    "base_unit_price": {"amount_minor": str(price.amount_minor)},
                }
                for component, component_product, price in rows
            ],
        )

    def _dto(self, product: Product, price: SitePrice | None = None, *, include_detail: bool = False) -> ProductAdminDTO:
        related_ids = self._variant_ids(product.id)
        values = {
            "id": product.id,
            "sku": product.sku,
            "slug": product.slug,
            "type": product.type,
            "title": product.title,
            "description": product.description,
            "active": product.active,
            "attributes": product.attributes_json,
            "seo": product.seo_json,
            "version": product.version,
            "price": None if price is None else {"amount_minor": str(price.amount_minor)},
            "original_price": None if price is None or getattr(price, "original_amount_minor", None) is None else {"amount_minor": str(price.original_amount_minor)},
            "related_product_ids": related_ids,
        }
        if include_detail:
            media = self.session.scalars(
                select(ProductMedia)
                .where(ProductMedia.product_id == product.id, ProductMedia.scan_state == "clean")
                .order_by(ProductMedia.position, ProductMedia.id)
            ).all()
            values["media"] = public_media(media)
            values["bundle"] = self._bundle_dto(product)
        return ProductAdminDTO(**values)

    def _variant_ids(self, product_id: UUID) -> list[UUID]:
        """Return both sides of the symmetric variant group relation."""
        outgoing = self.session.scalars(
            select(product_relations.c.related_product_id).where(product_relations.c.product_id == product_id)
        ).all()
        incoming = self.session.scalars(
            select(product_relations.c.product_id).where(product_relations.c.related_product_id == product_id)
        ).all()
        return sorted({value for value in [*outgoing, *incoming] if isinstance(value, UUID)})

    def _replace_variants(self, product_id: UUID, variant_ids: list[UUID]) -> None:
        """Persist a symmetric group so every variant can expose the chooser."""
        self.session.execute(
            product_relations.delete().where(
                (product_relations.c.product_id == product_id)
                | (product_relations.c.related_product_id == product_id)
            )
        )
        rows = [
            row
            for variant_id in variant_ids
            for row in (
                {"product_id": product_id, "related_product_id": variant_id},
                {"product_id": variant_id, "related_product_id": product_id},
            )
        ]
        if rows:
            self.session.execute(insert(product_relations), rows)

    def create_product(self, admin, command: ProductCreateDTO) -> ProductAdminDTO:
        """Create a catalog row and assign its SKU exactly once."""
        product_id = uuid4()
        slug = command.slug or self._slug(command.title, product_id)
        if command.related_product_ids and product_id in command.related_product_ids:
            raise HTTPException(422, detail="VALIDATION_ERROR")
        related = list(self.session.scalars(select(Product).where(Product.id.in_(command.related_product_ids)).order_by(Product.id))) if command.related_product_ids else []
        if len(related) != len(command.related_product_ids):
            raise HTTPException(422, detail="VALIDATION_ERROR")
        product = Product(
            id=product_id,
            sku=command.sku,
            slug=slug,
            type=command.type,
            title=command.title,
            description=command.description,
            active=command.active,
            attributes_json=command.attributes or {},
            seo_json=command.seo or {},
            version=1,
        )
        self.session.add(product)
        self.session.flush()
        if command.category_ids:
            from elton_database.models.catalog import Category
            categories = list(self.session.scalars(select(Category).where(Category.id.in_(command.category_ids))))
            if len(categories) != len(command.category_ids):
                raise HTTPException(422, detail="VALIDATION_ERROR")
            self.session.execute(insert(product_categories), [{"product_id": product.id, "category_id": category_id} for category_id in command.category_ids])
        if command.related_product_ids:
            self._replace_variants(product.id, command.related_product_ids)
        price = SitePrice(
            product_id=product.id,
            amount_minor=int(command.price.amount_minor),
            original_amount_minor=None if command.original_price is None else int(command.original_price.amount_minor),
            currency="RUB",
            version=1,
        )
        self.session.add(price)
        self.repo.audit(actor_id=admin.id, action="catalog.product.create", entity_type="product", entity_id=product.id, change_summary={"sku": product.sku}, trace_id=None)
        self.session.flush()
        return self._dto(product, price)

    @staticmethod
    def _slug(title: str, product_id: UUID) -> str:
        import re
        normalized = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return f"{normalized[:240] or 'product'}-{str(product_id).split('-')[0]}"

    def list_products(self, *, q: str, limit: int, cursor: str | None) -> ProductAdminPageDTO:
        """List site-owned catalog content, including inactive or unpriced rows."""
        signature = hashlib.sha256(json.dumps([q], ensure_ascii=False).encode()).hexdigest()
        offset = 0
        if cursor:
            try:
                decoded = json.loads(base64.b64decode(cursor.encode(), altchars=b"-_", validate=True))
                offset = decoded["offset"]
                if type(offset) is not int or not 0 <= offset <= 2147483647 or decoded["query"] != signature:
                    raise ValueError
            except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
                raise HTTPException(422, detail="VALIDATION_ERROR") from None
        statement = select(Product, SitePrice).outerjoin(SitePrice, SitePrice.product_id == Product.id)
        if q:
            needle = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            statement = statement.where(Product.title.ilike(needle, escape="\\") | Product.sku.ilike(needle, escape="\\"))
        rows = self.session.execute(statement.order_by(Product.title.asc(), Product.id).offset(offset).limit(limit + 1)).all()
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"offset": offset + limit, "query": signature}, separators=(",", ":")).encode()).decode()
        return ProductAdminPageDTO(items=[self._dto(product, price) for product, price in rows[:limit]], next_cursor=next_cursor)

    def get_product(self, product_id: UUID) -> ProductAdminDTO:
        row = self.session.execute(
            select(Product, SitePrice)
            .outerjoin(SitePrice, SitePrice.product_id == Product.id)
            .where(Product.id == product_id)
        ).first()
        if row is None:
            raise HTTPException(404, detail="NOT_FOUND")
        product, price = row
        return self._dto(product, price, include_detail=True)

    def get_bundle(self, product_id: UUID) -> BundleAdminDTO:
        product = self.session.get(Product, product_id)
        if product is None:
            raise HTTPException(404, detail="NOT_FOUND")
        result = self._bundle_dto(product)
        if result is None:
            raise HTTPException(404, detail="NOT_FOUND")
        return result

    def update_product(self, admin, product_id: UUID, patch: ProductWriteDTO, expected_version: int) -> ProductAdminDTO:
        product = self._product(product_id, expected_version)
        changed: dict = {}
        for field, column in (("title", "title"), ("description", "description"), ("active", "active"), ("attributes", "attributes_json"), ("seo", "seo_json")):
            value = getattr(patch, field)
            if value is not None:
                setattr(product, column, value)
                changed[field] = True
        if patch.related_product_ids is not None:
            related_ids = patch.related_product_ids
            if product.id in related_ids or len(related_ids) != len(set(related_ids)):
                raise HTTPException(422, detail="VALIDATION_ERROR")
            related_products = list(self.session.scalars(select(Product).where(Product.id.in_(related_ids)).order_by(Product.id))) if related_ids else []
            if len(related_products) != len(related_ids):
                raise HTTPException(422, detail="VALIDATION_ERROR")
            self._replace_variants(product.id, related_ids)
            changed["related_product_ids"] = True
        product.version += 1
        self.repo.audit(actor_id=admin.id, action="catalog.product.update", entity_type="product", entity_id=product.id, change_summary=changed, trace_id=None)
        return self._dto(product, self.session.get(SitePrice, product.id))

    def set_site_price(self, admin, product_id: UUID, command: SitePriceWriteDTO, expected_version: int) -> ProductAdminDTO:
        product = self._product(product_id, expected_version)
        price = self.session.scalar(select(SitePrice).where(SitePrice.product_id == product.id).with_for_update())
        amount = int(command.price.amount_minor)
        original_amount = None if command.original_price is None else int(command.original_price.amount_minor)
        if original_amount is not None and original_amount < amount:
            raise HTTPException(422, detail="VALIDATION_ERROR")
        if price is None:
            self.session.execute(insert(SitePrice).values(product_id=product.id, amount_minor=amount, original_amount_minor=original_amount, currency="RUB", version=1))
            price = self.session.scalar(select(SitePrice).where(SitePrice.product_id == product.id))
        else:
            price.amount_minor = amount
            price.original_amount_minor = original_amount
            price.version += 1
        product.version += 1
        self.repo.audit(actor_id=admin.id, action="catalog.site_price.update", entity_type="product", entity_id=product.id, change_summary={"price_changed": True}, trace_id=None)
        return self._dto(product, price)

    def replace_bundle(self, admin, product_id: UUID, command: BundleWriteDTO, expected_version: int) -> BundleAdminDTO:
        product = self._product(product_id, expected_version)
        if product.type != "bundle":
            raise HTTPException(409, detail="VALIDATION_ERROR")
        ids = [item.product_id for item in command.components]
        # PostgreSQL rejects FOR UPDATE on the nullable side of an OUTER JOIN.
        # Lock both relations separately in stable product-id order so a missing
        # price is validated without weakening the product/BOM race guard.
        product_rows = list(self.session.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id).with_for_update()))
        price_rows = list(self.session.scalars(select(SitePrice).where(SitePrice.product_id.in_(ids)).order_by(SitePrice.product_id).with_for_update()))
        products_by_id = {row.id: row for row in product_rows}
        prices_by_id = {row.product_id: row for row in price_rows}
        if len(product_rows) != len(ids) or any(product_row.type != "single" or not product_row.active or prices_by_id.get(product_row.id) is None or prices_by_id[product_row.id].amount_minor <= 0 for product_row in product_rows):
            raise HTTPException(422, detail="VALIDATION_ERROR")
        number = self.session.scalar(select(func.coalesce(func.max(BundleVersion.number), 0)).where(BundleVersion.product_id == product.id)) + 1
        version_id = uuid4()
        self.session.execute(insert(bundle_versions).values(id=version_id, product_id=product.id, number=number))
        for item in command.components:
            self.session.execute(insert(bundle_components).values(version_id=version_id, component_product_id=item.product_id, quantity=item.quantity))
        product.current_bundle_version_id = version_id
        product.version += 1
        components = [
            {"product_id": item.product_id, "sku": products_by_id[item.product_id].sku, "title": products_by_id[item.product_id].title, "quantity": item.quantity, "base_unit_price": {"amount_minor": str(prices_by_id[item.product_id].amount_minor)}}
            for item in command.components
        ]
        self.repo.audit(actor_id=admin.id, action="catalog.bundle.replace", entity_type="product", entity_id=product.id, change_summary={"component_count": len(components)}, trace_id=None)
        return BundleAdminDTO(version_id=version_id, version=number, components=components)


class AdminDraftService:
    def __init__(self, session: Session):
        self.session = session

    def list_drafts(self, admin, *, cursor: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, limit: int = 50, trace_id: str | None = None) -> DraftPageDTO:
        statement = select(CheckoutDraft).order_by(CheckoutDraft.created_at.desc(), CheckoutDraft.id.desc()).limit(limit + 1)
        if created_from is not None:
            statement = statement.where(CheckoutDraft.created_at >= created_from)
        if created_to is not None:
            statement = statement.where(CheckoutDraft.created_at <= created_to)
        if cursor:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
                created_at, draft_id = datetime.fromisoformat(decoded["created_at"]), UUID(decoded["id"])
            except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
                raise HTTPException(422, detail="VALIDATION_ERROR") from None
            statement = statement.where((CheckoutDraft.created_at < created_at) | ((CheckoutDraft.created_at == created_at) & (CheckoutDraft.id < draft_id)))
        rows = list(self.session.scalars(statement))
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = base64.urlsafe_b64encode(json.dumps({"created_at": last.created_at.isoformat(), "id": str(last.id)}, separators=(",", ":")).encode()).decode()
            rows = rows[:limit]
        self._audit_read(admin, "checkout_draft.list", None, trace_id)
        return DraftPageDTO(items=[{"id": row.id, "state": row.state, "channel": row.channel, "created_at": row.created_at, "goods_total": {"amount_minor": str(row.goods_total_minor)}, "contact": row.contact_snapshot, "address": row.address_snapshot} for row in rows], next_cursor=next_cursor)

    def get_draft(self, admin, draft_id: UUID, trace_id: str | None = None):
        row = self.session.scalar(select(CheckoutDraft).where(CheckoutDraft.id == draft_id))
        if row is None:
            raise HTTPException(404, detail="NOT_FOUND")
        self._audit_read(admin, "checkout_draft.read", row.id, trace_id)
        return {"id": row.id, "state": row.state, "channel": row.channel, "created_at": row.created_at, "goods_total": {"amount_minor": str(row.goods_total_minor)}, "contact": row.contact_snapshot, "address": row.address_snapshot}

    def _audit_read(self, admin, action: str, entity_id: UUID | None, trace_id: str | None) -> None:
        from elton_database.repositories.admin import AdminRepository
        AdminRepository(self.session).audit(actor_id=admin.id, action=action, entity_type="checkout_draft", entity_id=entity_id, change_summary={"read": True}, trace_id=trace_id)
