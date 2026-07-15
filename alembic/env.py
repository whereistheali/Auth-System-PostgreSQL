import os
import re
from logging.config import fileConfig

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError as SAOperationalError
from alembic import context

# ── App imports ─────────────────────────────────────────────────────────────
from app.core.config import settings
from app.db.base import Base
from app.models.password_reset import PasswordResetToken  # noqa: F401
from app.models.user import User  # noqa: F401

# ── Alembic config ───────────────────────────────────────────────────────────
config = context.config

# ── Inject DB URL from .env (sync driver for Alembic) ───────────────────────
SYNC_DB_URL = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
config.set_main_option("sqlalchemy.url", SYNC_DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _parse_db_url(url: str) -> dict:
    m = re.match(
        r"postgresql(?:\+\w+)?://(\w+):([^@]+)@([^:]+):(\d+)/(\w+)",
        url,
    )
    if not m:
        raise ValueError(f"Could not parse DATABASE_URL: {url}")
    return {
        "user": m.group(1),
        "password": m.group(2),
        "host": m.group(3),
        "port": int(m.group(4)),
        "database": m.group(5),
    }


def _ensure_db_exists():
    import subprocess as _sp

    info = _parse_db_url(settings.DATABASE_URL)

    def _try_connect():
        superuser = os.environ.get("POSTGRES_SUPERUSER", "postgres")
        superpass = os.environ.get("POSTGRES_SUPERUSER_PASSWORD", "")
        try:
            conn = psycopg2.connect(dbname="postgres", user=superuser, password=superpass)
        except psycopg2.OperationalError:
            conn = psycopg2.connect(
                dbname="postgres",
                user=superuser,
                password=superpass,
                host=info["host"],
                port=info["port"],
            )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn

    def _sudo_psql(sql):
        return _sp.run(
            ["sudo", "-u", "postgres", "psql", "-tAc", sql],
            capture_output=True, text=True, check=False,
        )

    try:
        conn = _try_connect()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (info["user"],))
        if not cur.fetchone():
            cur.execute(f"CREATE USER {info['user']} WITH PASSWORD %s", (info["password"],))
            print(f"Created user '{info['user']}'")
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (info["database"],))
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {info['database']} OWNER {info['user']}")
            print(f"Created database '{info['database']}'")
        cur.close()
        conn.close()
    except psycopg2.OperationalError:
        print("Falling back to sudo -u postgres ...")
        r = _sudo_psql(f"SELECT 1 FROM pg_roles WHERE rolname = '{info['user']}'")
        if r.stdout.strip() != "1":
            _sudo_psql(f"CREATE USER {info['user']} WITH PASSWORD '{info['password']}'")
            print(f"Created user '{info['user']}'")
        r = _sudo_psql(f"SELECT 1 FROM pg_database WHERE datname = '{info['database']}'")
        if r.stdout.strip() != "1":
            _sudo_psql(f"CREATE DATABASE {info['database']} OWNER {info['user']}")
            print(f"Created database '{info['database']}'")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    try:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    except SAOperationalError as e:
        if "does not exist" in str(e) or "FATAL" in str(e):
            print("Database or user not found — attempting to create...")
            _ensure_db_exists()
            connectable = engine_from_config(
                config.get_section(config.config_ini_section, {}),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    compare_server_default=True,
                )
                with context.begin_transaction():
                    context.run_migrations()
        else:
            raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()