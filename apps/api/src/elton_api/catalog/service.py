"""Catalog reads use the reviewed PostgreSQL tables and public DTOs."""
import base64
import hashlib
import json
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from elton_database.models.catalog import (
    BundleComponent, BundleVersion, Category, Collection, Product, ProductMedia,
    SitePrice, collection_items, product_categories, product_relations,
)
from elton_api.catalog.schemas import (
    BundleComponentDTO, BundleDTO, CategoryDTO, CollectionDetail, CollectionDTO,
    MediaDTO, Money, ProductDetail, ProductPage, ProductSummary,
)


def public_media(rows) -> list[MediaDTO]:
    result = []
    for row in rows:
        # Storage keys are server-selected relative paths, never import URLs.
        if row.scan_state != "clean" or not re.fullmatch(r"[A-Za-z0-9_/-]+\.[A-Za-z0-9]+", row.storage_key) or any(segment in {"", ".", ".."} for segment in row.storage_key.split("/")):
            continue
        result.append(MediaDTO(id=row.id, type=row.media_type, url=f"/api/v1/media/{row.storage_key}", alt_text=row.alt_text, position=row.position))
    # Public media has a stable presentation order: the first clean image is
    # the product thumbnail/hero, while video remains the final gallery item.
    result.sort(key=lambda item: (0 if item.type == "image" else 1, item.position, str(item.id)))
    return result


def product_summary(product, amount_minor: int, media, original_amount_minor: int | None = None) -> ProductSummary:
    clean = public_media(media)
    return ProductSummary(
        id=product.id,
        sku=product.sku,
        slug=product.slug,
        title=product.title,
        type=product.type,
        price=Money(amount_minor=str(amount_minor)),
        original_price=None if original_amount_minor is None else Money(amount_minor=str(original_amount_minor)),
        thumbnail=clean[0] if clean else None,
        version=product.version,
    )


class CatalogService:
    def __init__(self, session: Session):
        self.session = session

    def media(self, product_id: UUID):
        return self.session.scalars(select(ProductMedia).where(ProductMedia.product_id == product_id, ProductMedia.scan_state == "clean").order_by(ProductMedia.position, ProductMedia.id)).all()

    def categories(self) -> list[CategoryDTO]:
        return [CategoryDTO(id=x.id, slug=x.slug, title=x.title) for x in self.session.scalars(select(Category).order_by(Category.sort_order, Category.id))]

    def bundle(self, product: Product) -> BundleDTO | None:
        if product.type != "bundle" or not product.current_bundle_version_id:
            return None
        version = self.session.get(BundleVersion, product.current_bundle_version_id)
        if version is None or version.product_id != product.id:
            return None
        rows = self.session.execute(select(BundleComponent, Product, SitePrice).join(Product, Product.id == BundleComponent.component_product_id).outerjoin(SitePrice, SitePrice.product_id == Product.id).where(BundleComponent.version_id == version.id).order_by(Product.id)).all()
        if not rows or any(not p.active or p.type != "single" or price is None for _, p, price in rows):
            return None
        return BundleDTO(version_id=version.id, version=version.number, components=[BundleComponentDTO(product_id=p.id, sku=p.sku, title=p.title, quantity=c.quantity, base_unit_price=Money(amount_minor=str(price.amount_minor))) for c, p, price in rows])

    def detail(self, *, product_id: UUID | None = None, slug: str | None = None) -> ProductDetail:
        predicate = Product.id == product_id if product_id is not None else Product.slug == slug
        row = self.session.execute(select(Product, SitePrice).join(SitePrice, SitePrice.product_id == Product.id).where(predicate, Product.active.is_(True))).first()
        if row is None:
            raise HTTPException(404, detail="NOT_FOUND")
        product, price = row
        media = self.media(product.id)
        cats = self.session.scalars(select(Category).join(product_categories, product_categories.c.category_id == Category.id).where(product_categories.c.product_id == product.id).order_by(Category.sort_order, Category.id))
        outgoing = self.session.scalars(
            select(product_relations.c.related_product_id)
            .join(Product, Product.id == product_relations.c.related_product_id)
            .where(product_relations.c.product_id == product.id, Product.active.is_(True))
        ).all()
        incoming = self.session.scalars(
            select(product_relations.c.product_id)
            .join(Product, Product.id == product_relations.c.product_id)
            .where(product_relations.c.related_product_id == product.id, Product.active.is_(True))
        ).all()
        variant_ids = sorted({value for value in [*outgoing, *incoming] if isinstance(value, UUID)})
        return ProductDetail(**product_summary(product, price.amount_minor, media, getattr(price, "original_amount_minor", None)).model_dump(), description=product.description, categories=[CategoryDTO(id=x.id, slug=x.slug, title=x.title) for x in cats], attributes=product.attributes_json, seo=product.seo_json, media=public_media(media), related_product_ids=variant_ids, bundle=self.bundle(product))

    def products(self, *, q: str, category: str | None, sort: str, limit: int, cursor: str | None) -> ProductPage:
        signature = hashlib.sha256(json.dumps([q, category, sort], ensure_ascii=False).encode()).hexdigest()
        offset = 0
        if cursor:
            try:
                if len(cursor) > 512:
                    raise ValueError
                decoded = json.loads(base64.b64decode(cursor.encode(), altchars=b"-_", validate=True))
                offset = decoded["offset"]
                if type(offset) is not int or not 0 <= offset <= 2147483647 or decoded["query"] != signature:
                    raise ValueError
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise HTTPException(422, detail="VALIDATION_ERROR") from None
        statement = select(Product, SitePrice).join(SitePrice, SitePrice.product_id == Product.id).where(Product.active.is_(True))
        if q:
            # Escape SQL LIKE metacharacters: search is literal title/SKU text.
            needle = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            statement = statement.where(Product.title.ilike(needle, escape="\\") | Product.sku.ilike(needle, escape="\\"))
        if category:
            statement = statement.join(product_categories, product_categories.c.product_id == Product.id).join(Category, Category.id == product_categories.c.category_id).where(Category.slug == category)
        ordering = {"title_asc": Product.title.asc(), "price_asc": SitePrice.amount_minor.asc(), "price_desc": SitePrice.amount_minor.desc()}[sort]
        rows = self.session.execute(statement.order_by(ordering, Product.id).offset(offset).limit(limit + 1)).all()
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(json.dumps({"offset": offset + limit, "query": signature}, separators=(",", ":")).encode()).decode()
        return ProductPage(items=[product_summary(p, price.amount_minor, self.media(p.id), getattr(price, "original_amount_minor", None)) for p, price in rows[:limit]], next_cursor=next_cursor)

    def collections(self) -> list[CollectionDTO]:
        return [CollectionDTO(id=x.id, slug=x.slug, title=x.title) for x in self.session.scalars(select(Collection).order_by(Collection.sort_order, Collection.id))]

    def collection(self, collection_id: UUID) -> CollectionDetail:
        collection = self.session.get(Collection, collection_id)
        if collection is None:
            raise HTTPException(404, detail="NOT_FOUND")
        rows = self.session.execute(select(Product, SitePrice).join(collection_items, collection_items.c.product_id == Product.id).join(SitePrice, SitePrice.product_id == Product.id).where(collection_items.c.collection_id == collection_id, Product.active.is_(True)).order_by(collection_items.c.position, Product.id))
        return CollectionDetail(id=collection.id, slug=collection.slug, title=collection.title, items=[product_summary(p, price.amount_minor, self.media(p.id), getattr(price, "original_amount_minor", None)) for p, price in rows])
