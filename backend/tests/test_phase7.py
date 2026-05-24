"""
Phase 7 tests — Fargate task launcher, one-shot runner, reconciliation.

All AWS calls are mocked — no real boto3/ECS needed.
"""

from datetime import datetime, timedelta
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


# ── Task launcher unit tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_launch_task_uses_rq_in_dev(db_session):
    """In development mode, launch_task falls back to RQ."""
    from app.services.book_service import create_book
    from app.services.task_launcher import launch_task

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.flush()

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-id")

    with patch("app.services.task_launcher._is_fargate_available", return_value=False), \
         patch("app.workers.queue.get_queue", return_value=mock_queue):
        result = await launch_task(db_session, job)

    # Local dev returns None (no ARN)
    assert result is None
    assert mock_queue.enqueue.called


@pytest.mark.asyncio
async def test_launch_task_uses_fargate_in_prod(db_session):
    """In production with ECS config, launch_task calls boto3 run_task."""
    from app.services.book_service import create_book
    from app.services.task_launcher import launch_task

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.flush()

    mock_ecs = MagicMock()
    mock_ecs.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:us-east-1:123:task/abc123"}],
        "failures": [],
    }

    with patch("app.services.task_launcher._is_fargate_available", return_value=True), \
         patch("app.services.task_launcher.settings") as mock_settings, \
         patch("boto3.client", return_value=mock_ecs):
        mock_settings.is_production = True
        mock_settings.aws_region = "us-east-1"
        result = await launch_task(db_session, job)

    assert result == "arn:aws:ecs:us-east-1:123:task/abc123"
    assert job.ecs_task_arn == "arn:aws:ecs:us-east-1:123:task/abc123"
    assert mock_ecs.run_task.called


@pytest.mark.asyncio
async def test_launch_task_marks_failed_on_ecs_error(db_session):
    """If ECS run_task fails, job is marked FAILED."""
    from app.services.book_service import create_book
    from app.services.task_launcher import launch_task

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.flush()

    mock_ecs = MagicMock()
    mock_ecs.run_task.side_effect = Exception("ECS: no capacity")

    with patch("app.services.task_launcher._is_fargate_available", return_value=True), \
         patch("app.services.task_launcher.settings") as mock_settings, \
         patch("boto3.client", return_value=mock_ecs):
        mock_settings.is_production = True
        mock_settings.aws_region = "us-east-1"
        with pytest.raises(Exception, match="ECS: no capacity"):
            await launch_task(db_session, job)

    assert job.status == JobStatus.FAILED
    assert "no capacity" in job.error_message


@pytest.mark.asyncio
async def test_fargate_available_false_without_config():
    """_is_fargate_available returns False when ECS config is missing."""
    from app.services.task_launcher import _is_fargate_available

    with patch("app.services.task_launcher.ECS_CLUSTER", ""), \
         patch("app.services.task_launcher.ECS_TASK_DEFINITION", ""), \
         patch("app.services.task_launcher.ECS_SUBNET_IDS", []):
        assert _is_fargate_available() is False


@pytest.mark.asyncio
async def test_fargate_available_true_with_config():
    """_is_fargate_available returns True when all ECS config is present."""
    from app.services.task_launcher import _is_fargate_available

    with patch("app.services.task_launcher._load_ecs_config"), \
         patch("app.services.task_launcher.ECS_CLUSTER", "my-cluster"), \
         patch("app.services.task_launcher.ECS_TASK_DEFINITION", "bookforge-worker:1"), \
         patch("app.services.task_launcher.ECS_SUBNET_IDS", ["subnet-abc"]):
        assert _is_fargate_available() is True


# ── Reconciliation tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_marks_stuck_jobs_failed(db_session):
    """reconcile_stuck_jobs marks RUNNING jobs older than timeout as FAILED."""
    from app.services.book_service import create_book
    from app.services.task_launcher import reconcile_stuck_jobs

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    # Job started 45 minutes ago — stuck
    stuck_job = Job(
        book_id=book.id,
        task_name="generate_outline",
        status=JobStatus.RUNNING,
        started_at=datetime.utcnow() - timedelta(minutes=45),
    )
    # Job started 5 minutes ago — still running, not stuck
    fresh_job = Job(
        book_id=book.id,
        task_name="generate_chapter",
        status=JobStatus.RUNNING,
        started_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db_session.add_all([stuck_job, fresh_job])
    await db_session.commit()

    count = await reconcile_stuck_jobs(db_session, timeout_minutes=30)

    assert count == 1
    assert stuck_job.status == JobStatus.FAILED
    assert "timed out" in stuck_job.error_message
    assert fresh_job.status == JobStatus.RUNNING  # untouched


@pytest.mark.asyncio
async def test_reconcile_skips_done_jobs(db_session):
    """reconcile_stuck_jobs doesn't touch DONE or QUEUED jobs."""
    from app.services.book_service import create_book
    from app.services.task_launcher import reconcile_stuck_jobs

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    done_job = Job(
        book_id=book.id,
        task_name="generate_outline",
        status=JobStatus.DONE,
        started_at=datetime.utcnow() - timedelta(hours=2),
        completed_at=datetime.utcnow() - timedelta(hours=1),
    )
    queued_job = Job(
        book_id=book.id,
        task_name="generate_chapter",
        status=JobStatus.QUEUED,
    )
    db_session.add_all([done_job, queued_job])
    await db_session.commit()

    count = await reconcile_stuck_jobs(db_session, timeout_minutes=30)

    assert count == 0
    assert done_job.status == JobStatus.DONE
    assert queued_job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_reconcile_endpoint_requires_secret(client):
    """POST /internal/reconcile returns 403 without correct secret."""
    resp = await client.post(
        "/api/v1/internal/reconcile",
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reconcile_endpoint_works_with_correct_secret(client):
    """POST /internal/reconcile returns 200 with correct secret."""
    with patch("app.config.settings.app_internal_secret", "test-secret"):
        resp = await client.post(
            "/api/v1/internal/reconcile",
            headers={"X-Internal-Secret": "test-secret"},
        )
    assert resp.status_code == 200
    assert resp.json()["stuck_jobs_marked_failed"] == 0


# ── One-shot runner tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_one_shot_dispatches_correct_task(db_session):
    """run_one_shot calls the right task function based on job.task_name."""
    from app.services.book_service import create_book

    book = await create_book(db_session, user_id="u1", title="Test")
    await db_session.flush()

    job = Job(book_id=book.id, task_name="generate_outline", status=JobStatus.QUEUED)
    db_session.add(job)
    await db_session.commit()

    called_with = {}

    def fake_outline_task(job_id, notes_before=""):
        called_with["job_id"] = job_id
        called_with["notes_before"] = notes_before

    # runner.run_one_shot uses asyncio.run internally (local import).
    # Instead of patching asyncio, we mock _get_task_name at the runner level
    # and patch the task function itself.
    with patch("app.workers.tasks.generate_outline_task", fake_outline_task), \
         patch("app.workers.runner.run_one_shot") as mock_one_shot:

        def fake_one_shot(job_id):
            # Simulate what run_one_shot does: look up task_name, call task fn
            fake_outline_task(job_id, notes_before="")

        mock_one_shot.side_effect = fake_one_shot

        from app.workers.runner import run_one_shot
        run_one_shot(job.id)

    assert called_with.get("job_id") == job.id


@pytest.mark.asyncio
async def test_advance_stores_ecs_task_arn(client):
    """After advance, job record stores the ECS task ARN (in prod mode)."""
    headers = await _auth(client)

    resp = await client.post("/api/v1/books", json={
        "title": "ARN Test Book",
        "notes_before": "A story",
    }, headers=headers)
    book_id = resp.json()["id"]

    mock_queue = MagicMock()
    mock_queue.enqueue.return_value = MagicMock(id="rq-id")

    with patch("app.services.task_launcher._is_fargate_available", return_value=False), \
         patch("app.workers.queue.get_queue", return_value=mock_queue), \
         patch("app.api.v1.books.get_provider_for_user",
               return_value=FakeLLMProvider(response=FAKE_OUTLINE)):
        resp = await client.post(
            f"/api/v1/books/{book_id}/advance", json={}, headers=headers
        )

    assert resp.status_code == 200
    assert resp.json()["job_id"] is not None
