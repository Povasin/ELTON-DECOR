import asyncio
import os
import secrets
import socket
import sys

import pytest


@pytest.fixture(autouse=True)
def windows_selector_event_loop_policy():
    """Keep Starlette TestClient on a non-Proactor loop on Windows.

    AnyIO's blocking portal creates a socket pair while entering TestClient.
    The default Windows Proactor policy can hang in restricted runners before
    the ASGI app receives a request.  This test-only policy does not affect
    production startup or event-loop configuration.
    """
    if sys.platform != "win32":
        yield
        return

    previous_policy = asyncio.get_event_loop_policy()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        yield
    finally:
        asyncio.set_event_loop_policy(previous_policy)


@pytest.fixture
def settings_values():
    # Generated per test; no stored authentication or provider credentials.
    return {
        "mode": "foundation_demo",
        "guest_origins": ("http://localhost:3000",),
        "admin_origins": ("http://localhost:3001",),
        "session_csrf_key": secrets.token_urlsafe(32),
    }


@pytest.fixture
def unreachable_database_url():
    # Hold a bound, non-listening socket so the port cannot become a live PG.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield f"postgresql+psycopg://synthetic@127.0.0.1:{reserved.getsockname()[1]}/elton_test"


@pytest.fixture
def postgres_url():
    url = os.environ.get("ELTON_TEST_DATABASE_URL")
    if not url:
        pytest.skip("actual PostgreSQL unavailable: set ELTON_TEST_DATABASE_URL")
    return url
