"""Public catalog serialization and actual-PG HTTP queries."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from test_guest_cart import task_module, pg_runtime, pg_session, PRODUCT, BUNDLE
from elton_api.main import create_app
from sqlalchemy import text


def test_catalog_summary_reports_unknown_stock_and_omits_private_fields():
    service = task_module("elton_api.catalog.service")
    product = SimpleNamespace(id=uuid4(), sku="DEMO", slug="demo", title="Synthetic", type="single", version=1, cost=999, reviews=[5], fbo_quantity=99)
    data = service.product_summary(product, 10000, []).model_dump(mode="json")
    assert data["price"] == {"amount_minor": "10000", "currency": "RUB"}
    assert data["availability"] == {"state": "unknown", "quantity": None, "source": None, "observed_at": None}
    assert not set(data) & {"cost", "reviews", "fbo_quantity", "stock", "active"}


def test_catalog_thumbnail_uses_first_clean_image_before_video():
    service = task_module("elton_api.catalog.service")
    product = SimpleNamespace(id=uuid4(), sku="DEMO", slug="demo", title="Synthetic", type="single", version=1)
    video = SimpleNamespace(id=uuid4(), storage_key="clean/video.mp4", scan_state="clean", media_type="video", position=0, alt_text="Видео")
    image = SimpleNamespace(id=uuid4(), storage_key="clean/hero.webp", scan_state="clean", media_type="image", position=1, alt_text="Главное изображение")

    data = service.product_summary(product, 10000, [video, image])

    assert data.thumbnail is not None
    assert data.thumbnail.type == "image"
    assert data.thumbnail.url == "/api/v1/media/clean/hero.webp"


@pytest.mark.parametrize("amount", ["1.0", "01", "+1", "1e3", "-1", "9223372036854775808", 1, 1.0])
def test_money_schema_rejects_noncanonical_integer_money(amount):
    schemas = task_module("elton_api.catalog.schemas")
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        schemas.Money(amount_minor=amount)


def test_catalog_excludes_quarantined_and_unsafe_media_paths():
    service = task_module("elton_api.catalog.service")
    def media(key, state):
        return SimpleNamespace(id=uuid4(), storage_key=key, scan_state=state, media_type="image", position=1, alt_text="demo")
    result = service.public_media([media("demo.jpg", "clean"), media("secret.jpg", "quarantined"), media("../secret.jpg", "clean"), media("https://foreign.example/a", "clean")])
    assert len(result) == 1
    assert result[0].url == "/api/v1/media/demo.jpg"


@pytest.mark.postgres
def test_public_catalog_filters_paginates_and_serves_details_collections(pg_runtime):
    with TestClient(create_app(pg_runtime[0])) as client:
        categories = client.get("/api/v1/categories")
        assert categories.status_code == 200
        assert len(categories.json()["items"]) == 5
        response = client.get("/api/v1/products", params={"q": "DEMO", "sort": "price_asc", "limit": 1})
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        assert response.json()["items"][0]["id"] == str(PRODUCT)
        cursor = response.json()["next_cursor"]
        second = client.get("/api/v1/products", params={"q": "DEMO", "sort": "price_asc", "limit": 1, "cursor": cursor})
        assert second.json()["items"][0]["price"]["amount_minor"] == "20000"
        filtered = client.get("/api/v1/products", params={"category": "vases"}).json()
        assert len(filtered["items"]) == 1
        assert client.get("/api/v1/products", params={"limit": 101}).status_code == 422
        assert client.get("/api/v1/products", params={"cursor": "bad"}).status_code == 422
        by_id = client.get(f"/api/v1/products/{PRODUCT}")
        by_slug = client.get("/api/v1/products/by-slug/demo-flower")
        assert by_id.status_code == 200 and by_slug.json() == by_id.json()
        assert by_id.json()["delivery"] == {"state": "not_connected"}
        assert by_id.json()["related_product_ids"]
        assert client.get(f"/api/v1/products/{uuid4()}").status_code == 404
        bundle = client.get(f"/api/v1/products/{BUNDLE}").json()
        assert len(bundle["bundle"]["components"]) == 2
        collections = client.get("/api/v1/collections").json()
        detail = client.get('/api/v1/collections/' + collections["items"][0]["id"])
        assert detail.status_code == 200 and len(detail.json()["items"]) == 2
        with pg_session(pg_runtime) as session:
            session.execute(text("UPDATE products SET active=false WHERE id=:id"), {"id": PRODUCT})
        assert client.get(f"/api/v1/products/{PRODUCT}").status_code == 404
