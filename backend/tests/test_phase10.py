"""
Phase 10 tests — correlation ID, usage logging, health endpoint.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import patch

from app.db.session import Base, get_db
from app.db.redis import get_redis
from app.main import app


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    class FakeRedis:
        async def ping(self): return True
        async def aclose(self): pass

    async def override_redis():
        yield FakeRedis()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _auth(client) -> dict:
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com", "password": "password123"
    })
    r = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com", "password": "password123"
    })
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── Correlation ID tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_correlation_id_in_response_header(client):
    """Every response includes X-Correlation-ID."""
    resp = await client.get("/health")
    assert "x-correlation-id" in resp.headers
    assert len(resp.headers["x-correlation-id"]) > 0


@pytest.mark.asyncio
async def test_correlation_id_echoed_when_provided(client):
    """If the client sends a correlation ID, it's echoed back."""
    resp = await client.get("/health", headers={"X-Correlation-ID": "my-test-id-123"})
    assert resp.headers["x-correlation-id"] == "my-test-id-123"


@pytest.mark.asyncio
async def test_different_requests_get_different_ids(client):
    """Each request gets a unique correlation ID."""
    r1 = await client.get("/health")
    r2 = await client.get("/health")
    assert r1.headers["x-correlation-id"] != r2.headers["x-correlation-id"]


# ── Health endpoint tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_returns_checks(client):
    """Ready endpoint returns db and redis check results."""
    import unittest.mock as m

    mock_response = m.MagicMock()
    mock_response.status_code = 401  # OpenRouter returns 401 for missing key — still reachable

    mock_client = m.AsyncMock()
    mock_client.__aenter__ = m.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = m.AsyncMock(return_value=False)
    mock_client.get = m.AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await client.get("/ready")

    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    assert "db" in data["checks"]
    assert "redis" in data["checks"]


# ── Usage logging tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_usage_creates_record(db_engine):
    from app.services.usage_service import log_usage
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        entry = await log_usage(
            db,
            user_id="user-1",
            book_id="book-1",
            model="openai/gpt-4o-mini",
            stage="outline",
            prompt_tokens=500,
            completion_tokens=300,
            cost_usd=0.00062,
            duration_ms=1234,
        )
        await db.commit()

    assert entry.id is not None
    assert entry.user_id == "user-1"
    assert entry.model == "openai/gpt-4o-mini"
    assert entry.cost_usd == 0.00062


@pytest.mark.asyncio
async def test_get_usage_summary_empty(db_engine):
    from app.services.usage_service import get_usage_summary
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        summary = await get_usage_summary(db, "user-nobody")

    assert summary["total_calls"] == 0
    assert summary["total_cost_usd"] == 0.0
    assert summary["by_model"] == []
    assert summary["recent"] == []


@pytest.mark.asyncio
async def test_get_usage_summary_with_data(db_engine):
    from app.services.usage_service import log_usage, get_usage_summary
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        for _i in range(3):
            await log_usage(
                db,
                user_id="user-1",
                book_id=None,
                model="openai/gpt-4o-mini",
                stage="chapter",
                prompt_tokens=1000,
                completion_tokens=2000,
                cost_usd=0.005,
                duration_ms=2000,
            )
        await db.commit()
        summary = await get_usage_summary(db, "user-1")

    assert summary["total_calls"] == 3
    assert abs(summary["total_cost_usd"] - 0.015) < 0.0001
    assert len(summary["by_model"]) == 1
    assert summary["by_model"][0]["model"] == "openai/gpt-4o-mini"
    assert summary["by_model"][0]["calls"] == 3


@pytest.mark.asyncio
async def test_usage_isolated_per_user(db_engine):
    from app.services.usage_service import log_usage, get_usage_summary
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        await log_usage(db, user_id="user-a", book_id=None, model="gpt", stage="outline",
                        prompt_tokens=100, completion_tokens=100, cost_usd=0.01, duration_ms=100)
        await log_usage(db, user_id="user-b", book_id=None, model="gpt", stage="outline",
                        prompt_tokens=100, completion_tokens=100, cost_usd=0.02, duration_ms=100)
        await db.commit()

        summary_a = await get_usage_summary(db, "user-a")
        summary_b = await get_usage_summary(db, "user-b")

    assert summary_a["total_calls"] == 1
    assert summary_b["total_calls"] == 1
    assert summary_a["total_cost_usd"] != summary_b["total_cost_usd"]


# ── Usage API endpoint tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_usage_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_usage_endpoint_returns_summary(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_cost_usd" in data
    assert "total_calls" in data
    assert "by_model" in data
    assert "recent" in data


@pytest.mark.asyncio
async def test_usage_endpoint_accepts_days_param(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/usage?days=7", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["period_days"] == 7


@pytest.mark.asyncio
async def test_usage_endpoint_invalid_days(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/usage?days=0", headers=headers)
    assert resp.status_code == 422
