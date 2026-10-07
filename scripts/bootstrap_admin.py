"""Provision or reset the single local Stage 1 admin owner.

Run from a trusted local terminal after migrations. Password input is hidden and
is never accepted through command-line arguments, source files or stdout.
"""
from __future__ import annotations

import getpass
import os
import sys

from sqlalchemy import text

from elton_api.admin.auth import hash_password
from elton_api.config import Settings
from elton_database.repositories.admin import AdminRepository
from elton_database.session import get_session


def _email() -> str:
    value = input("Owner email: ").strip().lower()
    if not value or len(value) > 254 or "@" not in value:
        raise ValueError("A valid owner email is required")
    return value


def _interactive_password() -> str:
    first = getpass.getpass("New owner password: ")
    second = getpass.getpass("Repeat owner password: ")
    if first != second:
        raise ValueError("Passwords do not match")
    return first


def _password() -> str:
    """Read an ignored local secret file or fall back to hidden confirmation."""
    configured = os.environ.get("ELTON_ADMIN_PASSWORD_FILE")
    if not configured:
        return _interactive_password()
    path = os.path.abspath(configured)
    try:
        if os.path.islink(path) or not os.path.isfile(path):
            raise ValueError("password file must be a regular local file")
        with open(path, "r", encoding="utf-8", newline="") as secret_file:
            value = secret_file.read()
    except (OSError, UnicodeError) as error:
        raise ValueError("password file could not be read") from error
    # Permit the conventional single terminating newline, but never trim or
    # normalize password characters. Multiple lines cannot be an accidental
    # valid credential.
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n") or value.endswith("\r"):
        value = value[:-1]
    if "\r" in value or "\n" in value:
        raise ValueError("password file must contain one password")
    return value


def main() -> int:
    reset = "--reset" in sys.argv[1:]
    if any(arg != "--reset" for arg in sys.argv[1:]):
        raise SystemExit("Usage: python scripts/bootstrap_admin.py [--reset]")
    settings = Settings()
    email, password = _email(), _password()
    sessions = get_session(settings.database_url.get_secret_value())
    try:
        session = next(sessions)
        with session.begin():
            # Serializes bootstrap/reset across local invocations without
            # inventing another lock service.
            session.execute(text("SELECT pg_advisory_xact_lock(hashtext('elton-stage1-admin-owner'))"))
            repo = AdminRepository(session)
            existing = repo.owner_by_email(email)
            if reset:
                if existing is None or repo.owner_count() != 1:
                    raise ValueError("Reset requires the existing sole owner email")
                existing.password_hash = hash_password(password)
                repo.revoke_all_sessions(existing.id)
                repo.audit(actor_id=existing.id, action="admin.auth.reset", entity_type="admin_user", entity_id=existing.id, change_summary={"sessions_revoked": True}, trace_id=None)
                print("Owner password reset; existing sessions were revoked.")
            else:
                if repo.owner_count() != 0:
                    raise ValueError("An owner already exists; use --reset with that owner email")
                owner = repo.create_owner(email_normalized=email, password_hash=hash_password(password))
                repo.audit(actor_id=owner.id, action="admin.auth.bootstrap", entity_type="admin_user", entity_id=owner.id, change_summary={"permissions": 3}, trace_id=None)
                print("Local admin owner created. Sign in at the local admin URL.")
    finally:
        sessions.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyboardInterrupt) as error:
        print(f"Admin bootstrap was not applied: {error}", file=sys.stderr)
        raise SystemExit(2)
