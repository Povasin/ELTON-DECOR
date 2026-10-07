"""PostgreSQL sessions; schema creation belongs exclusively to Alembic."""

from collections.abc import Iterator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


def get_session(database_url: str | None = None) -> Iterator[Session]:
    """Yield a transactional session and release its connection on every exit.

    An explicit URL keeps independent application instances isolated. The
    zero-argument form uses the same runtime environment as API Settings.
    No schema creation or automatic commit is performed.
    """
    url = database_url or os.environ.get("ELTON_DATABASE_URL")
    if not url:
        raise RuntimeError("Runtime PostgreSQL configuration is required")
    engine = create_engine(
        url, poolclass=NullPool, echo=False, hide_parameters=True,
        connect_args={"connect_timeout": 2},
    )
    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()
