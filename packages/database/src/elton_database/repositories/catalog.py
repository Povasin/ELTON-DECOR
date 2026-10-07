"""Catalog reads and stable product locking; no saved-snapshot mutation API."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from elton_database.models.catalog import Product

CatalogRow = Product


class CatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def load_products(self, ids: list[UUID], for_update: bool = False) -> list[CatalogRow]:
        statement = select(Product).where(Product.id.in_(ids)).order_by(Product.id)
        if for_update:
            statement = statement.with_for_update()
        return list(self.session.scalars(statement))
