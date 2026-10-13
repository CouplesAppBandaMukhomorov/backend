import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-with-at-least-32-bytes-long")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import crypto
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.google_credential import GoogleCredential

PASSWORD = "supersecret"
GOOGLE_CLIENT_ID = "test-client-id"


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    def _headers(tokens: dict) -> dict:
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    return _headers


@pytest_asyncio.fixture
async def register(client):
    async def _register(
        email: str,
        password: str = PASSWORD,
        display_name: str = "Test User",
    ) -> dict:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": display_name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest_asyncio.fixture
async def make_couple(client, register, auth_headers):
    async def _make_couple(email: str = "owner@example.com") -> tuple[dict, dict, dict]:
        tokens = await register(email)
        headers = auth_headers(tokens)
        response = await client.post("/api/v1/couples", json={}, headers=headers)
        assert response.status_code == 201, response.text
        return tokens, headers, response.json()

    return _make_couple


@pytest_asyncio.fixture
async def connect_google(client, session_factory, auth_headers):
    async def _connect(tokens: dict) -> dict:
        headers = auth_headers(tokens)
        response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200, response.text
        user_id = uuid.UUID(response.json()["id"])

        async with session_factory() as session:
            session.add(
                GoogleCredential(
                    user_id=user_id,
                    access_token=crypto.encrypt("fake-access-token"),
                    refresh_token=crypto.encrypt("fake-refresh-token"),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    scope="https://www.googleapis.com/auth/calendar.events",
                )
            )
            await session.commit()

        return headers

    return _connect
