"""Explicit migration command, never invoked at application startup."""
import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url
from elton_database.models.catalog import Base
from elton_database.models import guest, drafts

config = context.config
target_metadata = Base.metadata


def run():
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    supplied = config.attributes.get("connection")
    if supplied is not None:
        if supplied.dialect.name != "postgresql":
            raise RuntimeError("Migrations require PostgreSQL")
        context.configure(connection=supplied, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = os.environ.get("ELTON_DATABASE_URL")
    if not url or make_url(url).get_backend_name() != "postgresql":
        raise RuntimeError("Runtime PostgreSQL configuration is required")
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run()
