"""Protected admin product detail contract tests."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from elton_api.admin.service import AdminCatalogService
from elton_api.config import Settings
from elton_api.main import create_app


class _Result:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def all(self):
        return self.value


class _DetailSession:
    def __init__(self, row, *, bundle=None, components=(), media=()):
        self.row = row
        self.bundle = bundle
        self.components = list(components)
        self.media = list(media)
        self._execute_calls = 0

    def execute(self, _statement):
        self._execute_calls += 1
        return _Result(self.row if self._execute_calls == 1 else self.components)

    def get(self, model, _identity):
        # The service asks for the current BOM version by model; no other get
        # is used by this read path.
        return self.bundle

    def scalars(self, _statement):
        return _Result(self.media)


def _product(*, product_type="single", active=True, bundle_id=None):
    return SimpleNamespace(
        id=uuid4(),
        sku="SYNTHETIC-SKU",
        slug="synthetic-product",
        type=product_type,
        title="Synthetic product",
        description="Synthetic description",
        active=active,
        attributes_json={"material": "glass"},
        seo_json={"title": "Synthetic"},
        version=4,
        current_bundle_version_id=bundle_id,
    )


def test_admin_detail_requires_catalog_read_session(settings_values, unreachable_database_url):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    product_id = uuid4()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/admin/products/{product_id}")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_admin_detail_keeps_inactive_product_visible_to_catalog_read():
    product = _product(active=False)
    service = AdminCatalogService(_DetailSession((product, None)))

    result = service.get_product(product.id)

    assert result.id == product.id
    assert result.active is False
    assert result.price is None
    assert result.media == []
    assert result.bundle is None


def test_admin_detail_contains_clean_media_and_bundle_shape():
    bundle_id = uuid4()
    product = _product(product_type="bundle", bundle_id=bundle_id)
    component = _product()
    component_price = SimpleNamespace(amount_minor=12900)
    version = SimpleNamespace(id=bundle_id, product_id=product.id, number=2)
    media = SimpleNamespace(
        id=uuid4(), storage_key="clean/synthetic.webp", scan_state="clean",
        media_type="image", position=0, alt_text="Synthetic image",
    )
    row = (product, SimpleNamespace(amount_minor=29900))
    service = AdminCatalogService(
        _DetailSession(
            row,
            bundle=version,
            components=[(SimpleNamespace(quantity=2), component, component_price)],
            media=[media],
        )
    )

    payload = service.get_product(product.id).model_dump(mode="json")

    assert payload["media"] == [{
        "id": str(media.id),
        "type": "image",
        "url": "/api/v1/media/clean/synthetic.webp",
        "alt_text": "Synthetic image",
        "position": 0,
    }]
    assert payload["bundle"]["version_id"] == str(bundle_id)
    assert payload["bundle"]["version"] == 2
    assert payload["bundle"]["components"][0]["quantity"] == 2
    assert payload["bundle"]["components"][0]["base_unit_price"] == {"amount_minor": "12900", "currency": "RUB"}
