from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from elton_api.catalog.schemas import CategoryPage, CollectionDetail, CollectionPage, ProductDetail, ProductPage
from elton_api.catalog.service import CatalogService
from elton_api.guest.service import database_session

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/categories", response_model=CategoryPage)
def categories(session: Session = Depends(database_session)) -> CategoryPage:
    return CategoryPage(items=CatalogService(session).categories())


@router.get("/products", response_model=ProductPage)
def products(q: str = "", category: str | None = None, sort: Literal["title_asc", "price_asc", "price_desc"] = "title_asc", limit: Annotated[int, Query(ge=1, le=100)] = 20, cursor: str | None = None, session: Session = Depends(database_session)) -> ProductPage:
    return CatalogService(session).products(q=q, category=category, sort=sort, limit=limit, cursor=cursor)


@router.get("/products/by-slug/{slug}", response_model=ProductDetail)
def by_slug(slug: str, session: Session = Depends(database_session)) -> ProductDetail:
    return CatalogService(session).detail(slug=slug)


@router.get("/products/{id}", response_model=ProductDetail)
def by_id(id: UUID, session: Session = Depends(database_session)) -> ProductDetail:
    return CatalogService(session).detail(product_id=id)


@router.get("/collections", response_model=CollectionPage)
def collections(session: Session = Depends(database_session)) -> CollectionPage:
    return CollectionPage(items=CatalogService(session).collections())


@router.get("/collections/{id}", response_model=CollectionDetail)
def collection(id: UUID, session: Session = Depends(database_session)) -> CollectionDetail:
    return CatalogService(session).collection(id)
