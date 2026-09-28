from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from src.infrastructure.database.models import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    import tomllib
    from pathlib import Path

    path = Path("config.toml")
    if path.exists():
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        settings = data.get("default", data)
        url = settings.get("Storage", {}).get("DatabasePath") or settings.get("DATABASE_URL")
        if url:
            parsed = make_url(url)
            if parsed.drivername.endswith("+aiosqlite"):
                parsed = parsed.set(drivername=parsed.drivername.replace("+aiosqlite", ""))
            return str(parsed)
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=database_url(),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
