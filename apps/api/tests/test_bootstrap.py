import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest


def bootstrap():
    try:
        config = importlib.import_module("elton_api.config")
        main = importlib.import_module("elton_api.main")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("elton_"):
            pytest.fail("Task 1 API bootstrap has not been implemented", pytrace=False)
        raise
    return config.Settings, main.create_app


def test_ready_requires_pg(settings_values, unreachable_database_url):
    """A constant healthy response must fail on a refused real PG connection."""
    Settings, create_app = bootstrap()
    settings = Settings(database_url=unreachable_database_url, **settings_values)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
        assert "synthetic" not in response.text


@pytest.mark.postgres
def test_ready_with_actual_pg(settings_values, postgres_url):
    """Refusing every connection must fail when an actual PG is available."""
    Settings, create_app = bootstrap()
    with TestClient(create_app(Settings(database_url=postgres_url, **settings_values))) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_foundation_has_no_provider_dependency(settings_values, unreachable_database_url, monkeypatch):
    """Startup must not depend on providers or advertise commercial capabilities."""
    for name in list(os.environ):
        if name.startswith(("OZON_", "SMS_", "SELLER_", "PERFORMANCE_")):
            monkeypatch.delenv(name)
    Settings, create_app = bootstrap()
    with TestClient(create_app(Settings(database_url=unreachable_database_url, **settings_values))) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json() == {
            "mode": "foundation_demo", "real_checkout": False, "payment": False,
            "delivery": False, "stock_reservation": False, "sms": False,
            "customer_account": False, "returns": False, "refunds": False, "reviews": False,
        }
        paths = client.get("/openapi.json").json()["paths"]
        assert {"/health/live", "/health/ready", "/api/v1/capabilities"} <= set(paths)
        assert not any(path.startswith(("/api/v1/orders", "/api/v1/auth/sms", "/api/v1/me", "/api/v1/provider")) for path in paths)
        preflight = client.options("/api/v1/capabilities", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET",
        })
        assert "access-control-allow-credentials" not in preflight.headers


@pytest.mark.parametrize("field", ["database_url", "guest_origins", "admin_origins", "session_csrf_key"])
def test_settings_require_runtime_configuration(field, settings_values, unreachable_database_url, monkeypatch):
    """A missing runtime requirement must not silently acquire a default."""
    Settings, _ = bootstrap()
    values = dict(settings_values, database_url=unreachable_database_url)
    values.pop(field)
    monkeypatch.delenv(f"ELTON_{field.upper()}", raising=False)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(**values)


@pytest.mark.parametrize("field,value", [
    ("mode", "commercial"), ("database_url", "sqlite:///demo.db"),
    ("guest_origins", ("*",)), ("admin_origins", ("https://admin.example",)),
    ("guest_origins", ("http://localhost:3000/",)), ("session_csrf_key", ""),
])
def test_settings_reject_unsafe_foundation_configuration(field, value, settings_values, unreachable_database_url):
    """Unsupported mode, non-PG storage and unreviewed origins must fail closed."""
    Settings, _ = bootstrap()
    values = dict(settings_values, database_url=unreachable_database_url)
    values[field] = value
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(**values)


def test_export_openapi_without_runtime_secrets(tmp_path):
    """Schema generation must work offline without weakening runtime config."""
    output = tmp_path / "openapi.json"
    root = Path(__file__).resolve().parents[3]
    env = {key: value for key, value in os.environ.items() if not key.startswith("ELTON_")}
    result = subprocess.run(
        [sys.executable, str(root / "scripts/export_openapi.py"), "--output", str(output)],
        cwd=root, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert {"/health/live", "/health/ready", "/api/v1/capabilities"} <= set(schema["paths"])
    assert not any(path.startswith(("/api/v1/orders", "/api/v1/auth/sms", "/api/v1/me", "/api/v1/provider")) for path in schema["paths"])
    assert schema["components"]["schemas"]["CapabilitiesDTO"]["properties"]["payment"]["const"] is False
