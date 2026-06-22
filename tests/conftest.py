import re
from collections.abc import AsyncGenerator
from typing import Any

import psycopg2
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_NAME = "test_auth_db"
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/auth_db", f"/{TEST_DB_NAME}")
SYNC_TEST_DATABASE_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")


def _ensure_test_db_exists():
    import subprocess

    m = re.match(r"postgresql\+asyncpg://(\w+):([^@]+)@([^:]+):(\d+)/", settings.DATABASE_URL)
    if not m:
        return
    user, password = m.group(1), m.group(2)

    def _sql(sql: str):
        return subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-tAc", sql],
            capture_output=True, text=True, check=False,
        )

    r = _sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{user}'")
    if r.stdout.strip() != "1":
        _sql(f"CREATE USER {user} WITH PASSWORD '{password}'")
    r = _sql(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'")
    if r.stdout.strip() != "1":
        _sql(f"CREATE DATABASE {TEST_DB_NAME} OWNER {user}")


_ensure_test_db_exists()

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db() -> AsyncGenerator[AsyncSession, Any]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, Any]:
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, Any]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def user_credentials(client: AsyncClient) -> dict:
    payload = {"email": "test@example.com", "password": "StrongPass1"}
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    tokens = resp.json()
    return {"email": payload["email"], "password": payload["password"], **tokens}
