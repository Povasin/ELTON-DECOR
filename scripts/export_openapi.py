"""Export only the active API without accessing a database or providers."""

import argparse
import json
from pathlib import Path
import secrets

from elton_api.config import Settings
from elton_api.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Schema-only configuration is explicit and never used to start a server.
    app = create_app(Settings(
        database_url="postgresql+psycopg://synthetic@127.0.0.1:1/elton_schema",
        guest_origins=("http://localhost:3000",),
        admin_origins=("http://localhost:3001",),
        session_csrf_key=secrets.token_urlsafe(32),
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
