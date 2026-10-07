"""Admin catalog contract tests; positive mutations require real PostgreSQL."""
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from elton_api.admin.schemas import BundleWriteDTO, ProductCreateDTO, ProductWriteDTO, SitePriceWriteDTO
from elton_api.catalog.schemas import Money


def test_catalog_commands_are_narrow_and_versioned():
    product = ProductWriteDTO.model_validate({"title": "Vase"})
    price = SitePriceWriteDTO.model_validate({"price": {"amount_minor": "9007199254740993"}})
    bundle = BundleWriteDTO.model_validate({"components": [{"product_id": str(uuid4()), "quantity": 2}]})
    assert product.title == "Vase"
    assert price.price.amount_minor == "9007199254740993"
    assert bundle.components[0].quantity == 2


def test_product_create_assigns_sku_and_patch_cannot_contain_it():
    command = ProductCreateDTO.model_validate({
        "sku": "NEW-VASE-001",
        "title": "Новая ваза",
        "price": {"amount_minor": "15000", "currency": "RUB"},
        "attributes": {"Материал": "Стекло", "Высота": "20 см"},
        "related_product_ids": [str(uuid4())],
    })
    assert command.sku == "NEW-VASE-001"
    assert command.attributes == {"Материал": "Стекло", "Высота": "20 см"}
    with pytest.raises(ValidationError):
        ProductWriteDTO.model_validate({"sku": "MUST-NOT-CHANGE", "title": "x"})


def test_site_price_supports_compare_at_price_in_rubles_and_validates_order():
    command = SitePriceWriteDTO.model_validate({
        "price": {"amount_minor": "15000"},
        "original_price": {"amount_minor": "20000"},
    })
    assert command.original_price.amount_minor == "20000"
    with pytest.raises(ValidationError):
        SitePriceWriteDTO.model_validate({
            "price": {"amount_minor": "20000"},
            "original_price": {"amount_minor": "15000"},
        })


def test_catalog_authoring_migration_adds_compare_at_checks():
    migration = Path(__file__).resolve().parents[3] / "packages" / "database" / "alembic" / "versions" / "0004_catalog_authoring.py"
    text = migration.read_text(encoding="utf-8")
    assert "original_amount_minor" in text
    assert "original_amount_minor >= amount_minor" in text


def test_bundle_command_rejects_duplicate_components_and_unknown_commercial_fields():
    component = str(uuid4())
    with pytest.raises(ValidationError):
        BundleWriteDTO.model_validate({"components": [{"product_id": component, "quantity": 1}, {"product_id": component, "quantity": 2}]})
    with pytest.raises(ValidationError):
        ProductWriteDTO.model_validate({"title": "x", "paid": True})


@pytest.mark.parametrize("field", ["paid", "provider_state", "nested"])
def test_nested_reserved_fields_are_rejected(field):
    payload = {"attributes": {field: {"payment_status": "captured"} if field == "nested" else "forbidden"}}
    with pytest.raises(ValidationError):
        ProductWriteDTO.model_validate(payload)


def test_site_price_must_be_positive():
    with pytest.raises(ValidationError):
        SitePriceWriteDTO.model_validate({"price": {"amount_minor": "0"}})


def test_version_is_transport_header_not_a_command_field():
    with pytest.raises(ValidationError):
        ProductWriteDTO.model_validate({"expected_version": 1, "title": "x"})
    with pytest.raises(ValidationError):
        SitePriceWriteDTO.model_validate({"expected_version": 1, "price": {"amount_minor": "1"}})


def test_admin_migration_is_additive_and_contains_no_bootstrap_identity():
    migration = Path(__file__).resolve().parents[3] / "packages" / "database" / "alembic" / "versions" / "0003_admin_access.py"
    text = migration.read_text(encoding="utf-8")
    assert "down_revision = \"0002_guest_drafts\"" in text
    assert "INSERT INTO ADMIN" not in text.upper()
    assert "password_hash" in text and "admin_sessions" in text and "audit_log" in text


def test_bundle_locking_does_not_use_for_update_on_nullable_outer_join():
    service = (Path(__file__).resolve().parents[1] / "src" / "elton_api" / "admin" / "service.py").read_text(encoding="utf-8")
    start = service.index("def replace_bundle")
    end = service.index("class AdminDraftService")
    locking = service[start:end]
    assert "outerjoin(SitePrice" not in locking
    assert "select(Product)" in locking and "select(SitePrice)" in locking
    assert "with_for_update()" in locking
