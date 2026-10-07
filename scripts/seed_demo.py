"""Explicit synthetic catalog seed; requires an already migrated local database."""
import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from elton_database.models.catalog import (
    bundle_components, bundle_versions, categories, collection_items, collections,
    product_categories, product_relations, products, site_prices,
)
from elton_database.session import get_session

DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "packages/database/fixtures/catalog.synthetic.json"


def seed_demo(session: Session, fixture_path: Path) -> None:
    """Add missing synthetic records atomically; never reset existing catalog edits.

    The caller owns commit/rollback. UUIDs in the fixture make repeats harmless.
    This command does not create schema or seed guest/contact/address records.
    """
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True:
        raise ValueError("Only an explicitly synthetic catalog fixture is permitted")
    allowed = {"synthetic", "categories", "products", "collections", "relations"}
    if set(fixture) - allowed:
        raise ValueError("Fixture contains unsupported catalog sections")
    def add(table, values):
        session.execute(insert(table).values(**values).on_conflict_do_nothing())
    for category in fixture["categories"]:
        add(categories, {**category, "id": UUID(category["id"])})
    for product in fixture["products"]:
        permitted = {"id", "sku", "slug", "type", "title", "description", "category_ids", "amount_minor", "components", "bundle_version_id", "attributes_json", "seo_json"}
        if set(product) - permitted:
            raise ValueError("Fixture contains unsupported product fields")
        product_id = UUID(product["id"])
        add(products, {key: (product_id if key == "id" else value) for key, value in product.items() if key in {"id", "sku", "slug", "type", "title", "description", "attributes_json", "seo_json"}})
        add(site_prices, dict(product_id=product_id, amount_minor=product["amount_minor"], currency="RUB"))
        for category_id in product["category_ids"]:
            add(product_categories, dict(product_id=product_id, category_id=UUID(category_id)))
    for product in fixture["products"]:
        if product["type"] != "bundle":
            continue
        product_id, version_id = UUID(product["id"]), UUID(product["bundle_version_id"])
        # Existing immutable versions are never patched by a repeated seed.
        if not session.scalar(select(bundle_versions.c.id).where(bundle_versions.c.id == version_id)):
            add(bundle_versions, dict(id=version_id, product_id=product_id, number=1))
            for component in product["components"]:
                add(bundle_components, dict(version_id=version_id, component_product_id=UUID(component["product_id"]), quantity=component["quantity"]))
        session.execute(update(products).where(products.c.id == product_id, products.c.current_bundle_version_id.is_(None)).values(current_bundle_version_id=version_id))
    for collection in fixture.get("collections", []):
        collection_id = UUID(collection["id"])
        add(collections, dict(id=collection_id, slug=collection["slug"], title=collection["title"]))
        for position, product_id in enumerate(collection["product_ids"]):
            add(collection_items, dict(collection_id=collection_id, product_id=UUID(product_id), position=position))
    for relation in fixture.get("relations", []):
        add(product_relations, {key: UUID(value) for key, value in relation.items()})
    session.flush()


def main():
    parser = argparse.ArgumentParser(description="Seed synthetic catalog into an explicitly configured PostgreSQL database")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    sessions = get_session()
    try:
        session = next(sessions)
        with session.begin():
            seed_demo(session, args.fixture)
    finally:
        sessions.close()


if __name__ == "__main__":
    main()
