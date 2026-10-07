"""Negative tests for the still gated ADM-01 boundary."""
from uuid import uuid4
from pathlib import Path
import importlib.util

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from elton_api.admin.auth import AdminLoginLimiter, AdminPrincipal, admin_csrf_token, admin_if_match, hash_password, require_admin_mutation, resolve_admin, verify_password
from elton_api.admin.schemas import ProductWriteDTO
from elton_api.config import Settings
from elton_api.main import create_app


def request_for(app, *, origin: str | None = "http://localhost:3001", cookie: str | None = None, guest: bool = False):
    from starlette.requests import Request
    headers = [] if origin is None else [(b"origin", origin.encode())]
    scope = {"type": "http", "method": "GET", "path": "/api/v1/admin/drafts", "raw_path": b"/api/v1/admin/drafts", "query_string": b"", "headers": headers, "client": ("127.0.0.1", 1), "scheme": "http", "app": app}
    if cookie:
        name = "elton_guest" if guest else "elton_admin_session"
        scope["headers"].append((b"cookie", f"{name}={cookie}".encode()))
    return Request(scope)


def test_admin_paths_register_approved_adm01_routes_but_no_provider_routes(settings_values, unreachable_database_url):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/checkout-drafts" in paths
    assert "/api/v1/admin/products/{product_id}" in paths
    assert "get" in paths["/api/v1/admin/products/{product_id}"]
    assert "/api/v1/admin/products/{product_id}/bundle" in paths
    assert "get" in paths["/api/v1/admin/products/{product_id}/bundle"]
    assert "/api/v1/admin/products" in paths
    assert "/api/v1/admin/auth/login" in paths
    assert "/api/v1/admin/auth/logout" in paths
    assert "/api/v1/admin/session" in paths
    assert not any("ozon" in path or "provider" in path for path in paths)


def test_logout_response_explicitly_sets_no_content_status(settings_values, unreachable_database_url, monkeypatch):
    from fastapi import Response
    from elton_api.admin import routes

    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    request = request_for(app)
    response = Response()
    principal = AdminPrincipal(uuid4(), uuid4(), frozenset({"catalog.read"}), "owner@localhost")
    monkeypatch.setattr(routes, "revoke_current_session", lambda *_args: None)

    result = routes.logout(request, response, principal, object())

    assert result is response
    assert result.status_code == 204
    assert result.headers["set-cookie"].startswith("elton_admin=")


def test_admin_catalog_list_requires_catalog_read_session(settings_values, unreachable_database_url):
    from fastapi.testclient import TestClient
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/products")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_admin_dependency_rejects_missing_or_guest_proof_without_db(settings_values, unreachable_database_url):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    with pytest.raises(HTTPException) as exc:
        resolve_admin(request_for(app))
    assert exc.value.status_code == 401
    assert exc.value.detail == "SESSION_REQUIRED"
    with pytest.raises(HTTPException) as exc:
        resolve_admin(request_for(app, cookie="guest-proof", guest=True))
    assert exc.value.status_code == 401
    assert exc.value.detail == "SESSION_REQUIRED"


def test_admin_mutation_rejects_wrong_origin_before_session_lookup(settings_values, unreachable_database_url):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    with pytest.raises(HTTPException) as exc:
        require_admin_mutation(request_for(app, origin="http://localhost:3000"), "catalog.write")
    assert exc.value.status_code == 403
    assert exc.value.detail == "FORBIDDEN"


@pytest.mark.parametrize("field", ["paid", "delivered", "fbo", "provider_id", "payment_status", "fulfillment_status"])
def test_product_command_rejects_provider_and_commercial_fields(field):
    payload = {"title": "Synthetic"}
    payload[field] = "forbidden"
    with pytest.raises(ValidationError):
        ProductWriteDTO.model_validate(payload)


def test_admin_csrf_token_is_session_bound(settings_values, unreachable_database_url):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    session_id = uuid4()
    token = admin_csrf_token(session_id, settings_values["session_csrf_key"])
    assert token and token != admin_csrf_token(uuid4(), settings_values["session_csrf_key"])


def test_admin_if_match_is_required_and_uses_quoted_decimal_versions():
    with pytest.raises(HTTPException) as missing:
        admin_if_match(None)
    assert missing.value.status_code == 428
    assert admin_if_match('"7"') == 7
    with pytest.raises(HTTPException) as malformed:
        admin_if_match("7")
    assert malformed.value.status_code == 422


def test_argon2id_hash_and_password_bounds_are_enforced():
    password = "correct local demo password"
    digest = hash_password(password)
    assert digest.startswith("$argon2id$")
    assert verify_password(digest, password)
    assert not verify_password(digest, "wrong password")
    with pytest.raises(ValueError):
        hash_password("short")


def test_admin_login_limiter_rejects_after_bounded_attempts():
    limiter = AdminLoginLimiter()
    limiter.check("ip:127.0.0.1", 1)
    with pytest.raises(HTTPException) as error:
        limiter.check("ip:127.0.0.1", 1)
    assert error.value.status_code == 429


def test_bootstrap_reads_single_password_from_runtime_file_without_prompt(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[3] / "scripts" / "bootstrap_admin.py"
    spec = importlib.util.spec_from_file_location("bootstrap_admin_for_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    secret = tmp_path / "admin-password.txt"
    secret.write_text("correct local demo password\n", encoding="utf-8")
    monkeypatch.setenv("ELTON_ADMIN_PASSWORD_FILE", str(secret))
    assert module._password() == "correct local demo password"
    secret.write_text("first\nsecond\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one password"):
        module._password()
