from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def database_url():
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is required for migrations.")
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    url = url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    url = url.replace("?ssl=require", "?sslmode=require").replace("&ssl=require", "&sslmode=require")
    return url


def run_migrations_offline():
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    url = database_url()
    from sqlalchemy.engine import make_url
    parsed_url = make_url(url)
    print(f"DEZNY_MIGRATION_TARGET host={parsed_url.host} database={parsed_url.database} driver={parsed_url.drivername}", flush=True)
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        identity = connection.exec_driver_sql("""
            SELECT current_database(), current_user, inet_server_addr()::text,
                   current_schema(), current_setting('search_path'),
                   to_regclass('public.ingestion_jobs')::text,
                   to_regclass('public.alembic_version')::text
        """).one()
        print(f"DEZNY_MIGRATION_DB_IDENTITY={identity!r}", flush=True)
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
