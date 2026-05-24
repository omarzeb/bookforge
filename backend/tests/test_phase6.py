"""
Phase 6 tests — async job queue, job status, SSE streaming.
RQ is mocked so no real Redis needed.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base, get_db
from app.db.redis import get_redis
from app.db.models import Job, JobStatus
from app.main import app
from tests.fake_provider import FakeLLMProvider

FAKE_OUTLINE = """
Chapter 1: The Beginning - Where it all starts
Chapter 2: The Middle - Things escalate
Chapter 3: The End - Resolution arrives
"""
FAKE_CHAPTER = "This is complete chapter content. Engaging and well-written prose."


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session


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


async def _auth(client: AsyncClient) -> dict:
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com", "password": "password123"
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com", "password": "password123"
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_book(client: AsyncClient, headers: dict, notes: str = "A story") -> str:
    resp = await client.post("/api/v1/books", json={
        "title": "Test Book", "notes_before": notes
    }, headers=headers)
    return resp.json()["id"]


async def _enqueue_and_get_job_id(client: AsyncClient, headers: dict, book_id: str) -> str:
    """Helper: enqueue outline job, return job_id."""
    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="fake-rq-id")

    with patch("app.services.job_service.get_queue", return_value=mock_queue), \
         patch("app.api.v1.books.get_provider_for_user",
               return_value=FakeLLMProvider(response=FAKE_OUTLINE)):
        resp = await client.post(
            f"/api/v1/books/{book_id}/advance", json={}, headers=headers
        )
    return resp.json()["job_id"]


# ── Job model tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_model_defaults(db_session):
    from app.services.book_service import create_book
    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.commit()

    assert job.id is not None
    assert job.status == JobStatus.QUEUED
    assert job.started_at is None
    assert job.completed_at is None
    assert job.streamed_output is None
    assert job.error_message is None


@pytest.mark.asyncio
async def test_job_status_transitions(db_session):
    from app.services.book_service import create_book
    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.commit()

    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    db_session.add(job)
    await db_session.commit()
    assert job.status == JobStatus.RUNNING

    job.status = JobStatus.DONE
    job.completed_at = datetime.utcnow()
    db_session.add(job)
    await db_session.commit()
    assert job.status == JobStatus.DONE
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_job_failed_stores_error(db_session):
    from app.services.book_service import create_book
    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    job = Job(
        book_id=book.id,
        task_name="generate_outline",
        status=JobStatus.FAILED,
        error_message="OpenRouter returned 402: out of credits",
        completed_at=datetime.utcnow(),
    )
    db_session.add(job)
    await db_session.commit()

    assert job.status == JobStatus.FAILED
    assert "402" in job.error_message


# ── Advance endpoint tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_advance_returns_job_id(client):
    headers = await _auth(client)
    book_id = await _create_book(client, headers)
    job_id = await _enqueue_and_get_job_id(client, headers, book_id)

    assert job_id is not None
    assert isinstance(job_id, str)


@pytest.mark.asyncio
async def test_advance_message_describes_action(client):
    headers = await _auth(client)
    book_id = await _create_book(client, headers)

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="fake-rq-id")

    with patch("app.services.job_service.get_queue", return_value=mock_queue), \
         patch("app.api.v1.books.get_provider_for_user",
               return_value=FakeLLMProvider(response=FAKE_OUTLINE)):
        resp = await client.post(
            f"/api/v1/books/{book_id}/advance", json={}, headers=headers
        )

    assert "outline" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_advance_book_status_unchanged_while_queued(client):
    headers = await _auth(client)
    book_id = await _create_book(client, headers)

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="fake-rq-id")

    with patch("app.services.job_service.get_queue", return_value=mock_queue), \
         patch("app.api.v1.books.get_provider_for_user",
               return_value=FakeLLMProvider(response=FAKE_OUTLINE)):
        resp = await client.post(
            f"/api/v1/books/{book_id}/advance", json={}, headers=headers
        )

    assert resp.json()["book"]["status"] == "INPUT_RECEIVED"


# ── Job status endpoint tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_status(client):
    headers = await _auth(client)
    book_id = await _create_book(client, headers)
    job_id = await _enqueue_and_get_job_id(client, headers, book_id)

    resp = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert data["book_id"] == book_id
    assert data["task_name"] == "generate_outline"
    assert data["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_get_job_not_found(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/jobs/nonexistent-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_requires_auth(client):
    resp = await client.get("/api/v1/jobs/some-job-id")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cannot_access_other_users_job(client):
    await client.post("/api/v1/auth/register", json={"email": "u1@x.com", "password": "pass"})
    r1 = await client.post("/api/v1/auth/login", data={"username": "u1@x.com", "password": "pass"})
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "u2@x.com", "password": "pass"})
    r2 = await client.post("/api/v1/auth/login", data={"username": "u2@x.com", "password": "pass"})
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    book_id = await _create_book(client, h1)
    job_id = await _enqueue_and_get_job_id(client, h1, book_id)

    resp = await client.get(f"/api/v1/jobs/{job_id}", headers=h2)
    assert resp.status_code == 404


# ── SSE streaming tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_stream_returns_event_stream(client, db_engine):
    """Stream returns correct content-type. Job is pre-set to DONE to avoid polling hang."""
    headers = await _auth(client)
    book_id = await _create_book(client, headers)
    job_id = await _enqueue_and_get_job_id(client, headers, book_id)

    # Pre-complete the job so the stream closes immediately
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        job = await session.get(Job, job_id)
        job.status = JobStatus.DONE
        job.streamed_output = "Chapter 1: The Beginning"
        job.completed_at = datetime.utcnow()
        session.add(job)
        await session.commit()

    resp = await client.get(f"/api/v1/jobs/{job_id}/stream", headers=headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_sse_stream_emits_done_event(client, db_engine):
    """Stream emits DONE status and done sentinel when job is already complete."""
    headers = await _auth(client)
    book_id = await _create_book(client, headers)
    job_id = await _enqueue_and_get_job_id(client, headers, book_id)

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        job = await session.get(Job, job_id)
        job.status = JobStatus.DONE
        job.streamed_output = "Chapter 1: The Beginning\nChapter 2: The Middle"
        job.completed_at = datetime.utcnow()
        session.add(job)
        await session.commit()

    resp = await client.get(f"/api/v1/jobs/{job_id}/stream", headers=headers)
    assert resp.status_code == 200

    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]

    assert len(events) > 0
    assert any(e["status"] == "DONE" for e in events)
    assert any(e.get("done") is True for e in events)


@pytest.mark.asyncio
async def test_sse_stream_failed_job_emits_error(client, db_engine):
    """Stream emits error info when job has already failed."""
    headers = await _auth(client)
    book_id = await _create_book(client, headers)
    job_id = await _enqueue_and_get_job_id(client, headers, book_id)

    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        job = await session.get(Job, job_id)
        job.status = JobStatus.FAILED
        job.error_message = "OutOfCredits: no credits remaining"
        job.completed_at = datetime.utcnow()
        session.add(job)
        await session.commit()

    resp = await client.get(f"/api/v1/jobs/{job_id}/stream", headers=headers)
    assert resp.status_code == 200

    events = [
        json.loads(line[6:])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]

    failed_events = [e for e in events if e["status"] == "FAILED"]
    assert len(failed_events) > 0
    assert "error" in failed_events[0]


# ── Job service unit tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_outline_creates_job_record(db_session):
    from app.services.book_service import create_book
    from app.services.job_service import enqueue_outline

    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-123")

    with patch("app.services.job_service.get_queue", return_value=mock_queue):
        job = await enqueue_outline(db_session, book, notes_before="notes")

    assert job.id is not None
    assert job.book_id == book.id
    assert job.task_name == "generate_outline"
    assert job.status == JobStatus.QUEUED
    assert mock_queue.enqueue.called


@pytest.mark.asyncio
async def test_enqueue_chapter_creates_job_record(db_session):
    from app.services.book_service import create_book
    from app.services.job_service import enqueue_chapter

    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-456")

    with patch("app.services.job_service.get_queue", return_value=mock_queue):
        job = await enqueue_chapter(db_session, book, chapter_number=3)

    assert job.task_name == "generate_chapter"
    assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_enqueue_compile_creates_job_record(db_session):
    from app.services.book_service import create_book
    from app.services.job_service import enqueue_compile

    book = await create_book(db_session, user_id="user-1", title="Test")
    await db_session.flush()

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-789")

    with patch("app.services.job_service.get_queue", return_value=mock_queue):
        job = await enqueue_compile(db_session, book)

    assert job.task_name == "compile_book"
    assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_get_job_returns_none_for_missing(db_session):
    from app.services.job_service import get_job
    result = await get_job(db_session, "nonexistent-id")
    assert result is None
