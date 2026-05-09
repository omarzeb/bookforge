"""
Phase 5 integration tests — full book lifecycle via HTTP endpoints.
Uses AsyncClient against the real FastAPI app with an in-memory SQLite DB.
No real LLM calls — FakeLLMProvider is injected via dependency override.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base, get_db
from app.db.redis import get_redis
from app.main import app
from app.providers.factory import get_provider_for_user
from app.db.models import User
from tests.fake_provider import FakeLLMProvider

FAKE_OUTLINE = """
Chapter 1: The Beginning - Where it all starts
Chapter 2: The Middle - Things get complex
Chapter 3: The End - Resolution
"""
FAKE_CHAPTER = "This is the full chapter content. Engaging and well-written."


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


async def _register_and_login(client: AsyncClient) -> str:
    """Register a user and return the auth token."""
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com",
        "password": "password123",
    })
    return resp.json()["access_token"]


# ── Auth tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "password123",
    })
    assert resp.status_code == 201
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com", "password": "pass123"
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "login@example.com", "password": "pass123"
    })
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    body = {"email": "dup@example.com", "password": "pass123"}
    await client.post("/api/v1/auth/register", json=body)
    resp = await client.post("/api/v1/auth/register", json=body)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/books")
    assert resp.status_code == 401


# ── Book CRUD tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_book(client):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/books", json={
        "title": "My Test Book",
        "notes_before": "A story about adventure",
    }, headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Test Book"
    assert data["status"] == "INPUT_RECEIVED"


@pytest.mark.asyncio
async def test_list_books(client):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/v1/books", json={"title": "Book 1"}, headers=headers)
    await client.post("/api/v1/books", json={"title": "Book 2"}, headers=headers)

    resp = await client.get("/api/v1/books", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_book(client):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/books", json={"title": "Get Me"}, headers=headers)
    book_id = create.json()["id"]

    resp = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == book_id


@pytest.mark.asyncio
async def test_delete_book(client):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/books", json={"title": "Delete Me"}, headers=headers)
    book_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/books/{book_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_access_other_users_book(client):
    # User 1
    await client.post("/api/v1/auth/register", json={"email": "u1@x.com", "password": "pass"})
    r1 = await client.post("/api/v1/auth/login", data={"username": "u1@x.com", "password": "pass"})
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    # User 2
    await client.post("/api/v1/auth/register", json={"email": "u2@x.com", "password": "pass"})
    r2 = await client.post("/api/v1/auth/login", data={"username": "u2@x.com", "password": "pass"})
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    # User 1 creates a book
    create = await client.post("/api/v1/books", json={"title": "Private"}, headers=h1)
    book_id = create.json()["id"]

    # User 2 tries to access it
    resp = await client.get(f"/api/v1/books/{book_id}", headers=h2)
    assert resp.status_code == 404


# ── Full lifecycle integration test ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_book_lifecycle(client):
    """
    Complete HTTP flow:
    create → advance (generates outline) → approve outline
    → advance (generates chapters) → approve all chapters
    → advance (compiles) → COMPLETE
    """
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create book
    resp = await client.post("/api/v1/books", json={
        "title": "Integration Test Book",
        "notes_before": "A three-chapter adventure story",
    }, headers=headers)
    assert resp.status_code == 201
    book_id = resp.json()["id"]

    import app.services.orchestrator as orch_module
    import app.api.v1.books as books_module
    from unittest.mock import patch

    # Patch get_provider_for_user so it returns FakeLLMProvider regardless of user key
    with patch.object(books_module, "get_provider_for_user",
                      return_value=FakeLLMProvider(response=FAKE_OUTLINE)):

        # 2. Advance → generates outline, stops at OUTLINE_REVIEW
        resp = await client.post(f"/api/v1/books/{book_id}/advance", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "OUTLINE_REVIEW"
        assert resp.json()["outline_raw"] is not None

        # 3. Approve outline
        resp = await client.post(f"/api/v1/books/{book_id}/outline/approve", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "CHAPTERS_GENERATING"

    # 4. Advance → generates chapters (use chapter content response)
    with patch.object(books_module, "get_provider_for_user",
                      return_value=FakeLLMProvider(response=FAKE_CHAPTER)):

        resp = await client.post(f"/api/v1/books/{book_id}/advance", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "CHAPTER_REVIEW"

        # 5. Get chapters and approve all
        resp = await client.get(f"/api/v1/books/{book_id}/chapters", headers=headers)
        assert resp.status_code == 200
        chapters = resp.json()
        assert len(chapters) == 3

        for ch in chapters:
            resp = await client.post(
                f"/api/v1/books/{book_id}/chapters/{ch['number']}/approve",
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["approved"] is True

        # 6. Advance → all approved → compiles → COMPLETE
        resp = await client.post(f"/api/v1/books/{book_id}/advance", json={}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "COMPLETE"
