"""
Phase 8 tests — prompt families, prompts API, cost estimation, model tiers.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base, get_db
from app.db.redis import get_redis
from app.main import app


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


async def _auth(client: AsyncClient) -> dict:
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com", "password": "password123"
    })
    resp = await client.post("/api/v1/auth/login", data={
        "username": "test@example.com", "password": "password123"
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Prompt family resolver tests ──────────────────────────────────────────────

def test_resolver_maps_gpt_models():
    from app.prompts import _family
    assert _family("openai/gpt-4o") == "gpt"
    assert _family("openai/gpt-4o-mini") == "gpt"


def test_resolver_maps_gemini_models():
    from app.prompts import _family
    assert _family("google/gemini-pro-1.5") == "gemini"
    assert _family("google/gemini-flash-1.5") == "gemini"


def test_resolver_maps_deepseek_models():
    from app.prompts import _family
    assert _family("deepseek/deepseek-chat") == "deepseek"


def test_resolver_maps_claude_models():
    from app.prompts import _family
    assert _family("anthropic/claude-3.5-sonnet") == "claude"
    assert _family("anthropic/claude-3-opus") == "claude"


def test_resolver_defaults_for_unknown():
    from app.prompts import _family
    assert _family("unknown/model-xyz") == "defaults"


def test_resolver_falls_back_to_defaults_for_missing_family():
    """If a family doesn't have a stage module, falls back to defaults."""
    from app.prompts import resolve_outline
    # All families have outline, so test with a valid but uncommon one
    result = resolve_outline(
        model_id="meta-llama/llama-3.1-8b-instruct",
        title="Test Book",
        notes_before="Adventure story",
    )
    assert "system" in result
    assert "user" in result


# ── GPT prompt family tests ───────────────────────────────────────────────────

def test_gpt_outline_prompt():
    from app.prompts.gpt.outline import get
    result = get("Test Book", "An adventure story")
    assert "Test Book" in result["user"]
    assert "adventure" in result["user"]
    assert result["system"]


def test_gpt_chapter_prompt():
    from app.prompts.gpt.chapter import get
    result = get(
        book_title="Test Book",
        outline="Chapter 1: Beginning",
        chapter_title="The Beginning",
        chapter_number=1,
        previous_summaries=[],
    )
    assert "Test Book" in result["user"]
    assert "Chapter 1" in result["user"]
    assert "no preamble" in result["system"].lower() or "preamble" in result["system"].lower()


def test_gpt_chapter_includes_previous_summaries():
    from app.prompts.gpt.chapter import get
    result = get(
        book_title="Test",
        outline="Ch1\nCh2",
        chapter_title="Chapter 2",
        chapter_number=2,
        previous_summaries=[{
            "chapter_number": 1,
            "chapter_title": "Beginning",
            "summary": "Hero starts journey",
        }],
    )
    assert "Hero starts journey" in result["user"]


def test_gpt_revision_prompt():
    from app.prompts.gpt.chapter_revision import get
    result = get(
        book_title="Test",
        outline="...",
        chapter_title="Ch1",
        chapter_number=1,
        previous_summaries=[],
        original_content="Original text here.",
        editor_notes="Make it more dramatic.",
    )
    assert "Original text here" in result["user"]
    assert "more dramatic" in result["user"]


def test_gpt_summary_prompt():
    from app.prompts.gpt.summary import get
    result = get("Chapter content here.", 1, "The Beginning")
    assert "Chapter content here" in result["user"]


# ── Gemini prompt family tests ────────────────────────────────────────────────

def test_gemini_outline_has_numbered_instructions():
    from app.prompts.gemini.outline import get
    result = get("Test Book", "A mystery story")
    # Gemini family uses numbered instruction style
    assert "1." in result["system"] or "Format" in result["system"]


def test_gemini_chapter_has_rules():
    from app.prompts.gemini.chapter import get
    result = get(
        book_title="Test",
        outline="outline",
        chapter_title="Ch1",
        chapter_number=1,
        previous_summaries=[],
    )
    assert "Rules" in result["system"] or "rules" in result["system"]


# ── DeepSeek prompt family tests ──────────────────────────────────────────────

def test_deepseek_outline_is_concise():
    from app.prompts.deepseek.outline import get
    result = get("Test Book", "Sci-fi adventure")
    # DeepSeek prompts are deliberately short
    assert len(result["system"]) < 200


def test_deepseek_chapter_is_concise():
    from app.prompts.deepseek.chapter import get
    result = get(
        book_title="Test",
        outline="outline",
        chapter_title="Ch1",
        chapter_number=1,
        previous_summaries=[],
    )
    assert len(result["system"]) < 200


# ── User override tests ───────────────────────────────────────────────────────

def test_user_override_replaces_system_prompt():
    from app.prompts import resolve_outline
    result = resolve_outline(
        model_id="openai/gpt-4o",
        title="Test",
        notes_before="notes",
        user_override="MY CUSTOM SYSTEM PROMPT",
    )
    assert result["system"] == "MY CUSTOM SYSTEM PROMPT"


def test_user_override_works_for_all_stages():
    from app.prompts import resolve_chapter, resolve_chapter_revision, resolve_summary

    r1 = resolve_chapter(
        model_id="openai/gpt-4o", book_title="T", outline="o",
        chapter_title="c", chapter_number=1, previous_summaries=[],
        user_override="CUSTOM CHAPTER",
    )
    assert r1["system"] == "CUSTOM CHAPTER"

    r2 = resolve_summary(
        model_id="openai/gpt-4o", chapter_content="c",
        chapter_number=1, chapter_title="t", user_override="CUSTOM SUMMARY",
    )
    assert r2["system"] == "CUSTOM SUMMARY"


# ── Prompts API endpoint tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_prompts_empty(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/prompts", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_save_and_get_prompt_override(client):
    headers = await _auth(client)

    resp = await client.put("/api/v1/prompts/outline", json={
        "prompt_text": "You are an expert outline creator. Be concise."
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["stage"] == "outline"

    resp = await client.get("/api/v1/prompts/outline", headers=headers)
    assert resp.status_code == 200
    assert "outline creator" in resp.json()["prompt_text"]


@pytest.mark.asyncio
async def test_update_existing_prompt_override(client):
    headers = await _auth(client)

    await client.put("/api/v1/prompts/chapter", json={
        "prompt_text": "First version prompt."
    }, headers=headers)

    resp = await client.put("/api/v1/prompts/chapter", json={
        "prompt_text": "Updated version prompt."
    }, headers=headers)
    assert resp.status_code == 200
    assert "Updated" in resp.json()["prompt_text"]


@pytest.mark.asyncio
async def test_delete_prompt_override(client):
    headers = await _auth(client)

    await client.put("/api/v1/prompts/summary", json={
        "prompt_text": "Custom summary prompt."
    }, headers=headers)

    resp = await client.delete("/api/v1/prompts/summary", headers=headers)
    assert resp.status_code == 204

    resp = await client.get("/api/v1/prompts/summary", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_stage_returns_404(client):
    headers = await _auth(client)
    resp = await client.put("/api/v1/prompts/invalid_stage", json={
        "prompt_text": "some text"
    }, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_empty_prompt_returns_422(client):
    headers = await _auth(client)
    resp = await client.put("/api/v1/prompts/outline", json={
        "prompt_text": "   "
    }, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_default_prompt(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/prompts/defaults/outline", headers=headers)
    assert resp.status_code == 200
    assert "system_prompt" in resp.json()
    assert len(resp.json()["system_prompt"]) > 10


@pytest.mark.asyncio
async def test_prompt_override_isolated_per_user(client):
    """User A's overrides don't affect User B."""
    await client.post("/api/v1/auth/register", json={"email": "a@x.com", "password": "pass"})
    r_a = await client.post("/api/v1/auth/login", data={"username": "a@x.com", "password": "pass"})
    h_a = {"Authorization": f"Bearer {r_a.json()['access_token']}"}

    await client.post("/api/v1/auth/register", json={"email": "b@x.com", "password": "pass"})
    r_b = await client.post("/api/v1/auth/login", data={"username": "b@x.com", "password": "pass"})
    h_b = {"Authorization": f"Bearer {r_b.json()['access_token']}"}

    await client.put("/api/v1/prompts/outline", json={"prompt_text": "User A prompt"}, headers=h_a)

    resp = await client.get("/api/v1/prompts/outline", headers=h_b)
    assert resp.status_code == 404  # B has no override


# ── Model tiers + cost estimation tests ──────────────────────────────────────

def test_curated_models_have_required_fields():
    from app.services.model_tiers import CURATED_MODELS
    for m in CURATED_MODELS:
        assert m.model_id
        assert m.name
        assert m.tier in ("Recommended", "Budget", "Premium", "Other")
        assert m.context_k > 0


def test_estimate_book_cost_returns_range():
    from app.services.model_tiers import estimate_book_cost
    result = estimate_book_cost(
        chapters=10,
        prompt_price_per_1k=0.003,
        completion_price_per_1k=0.015,
    )
    assert result["low"] is not None
    assert result["high"] is not None
    assert result["low"] < result["high"]
    assert result["currency"] == "USD"


def test_estimate_book_cost_returns_none_without_pricing():
    from app.services.model_tiers import estimate_book_cost
    result = estimate_book_cost(chapters=10)
    assert result["low"] is None
    assert result["high"] is None


def test_get_curated_model_found():
    from app.services.model_tiers import get_curated_model
    m = get_curated_model("anthropic/claude-3.5-sonnet")
    assert m is not None
    assert m.tier == "Recommended"


def test_get_curated_model_not_found():
    from app.services.model_tiers import get_curated_model
    assert get_curated_model("unknown/model") is None


@pytest.mark.asyncio
async def test_curated_models_endpoint(client):
    headers = await _auth(client)
    resp = await client.get("/api/v1/models/curated", headers=headers)
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) > 0
    tiers = {m["tier"] for m in models}
    assert "Recommended" in tiers


@pytest.mark.asyncio
async def test_cost_estimate_endpoint_no_pricing(client):
    """Returns None costs when model not in cache."""
    headers = await _auth(client)
    resp = await client.get(
        "/api/v1/models/estimate?model_id=anthropic/claude-3.5-sonnet&chapters=10",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chapters"] == 10
    # No pricing in cache yet → None
    assert data["low_usd"] is None


@pytest.mark.asyncio
async def test_cost_estimate_invalid_chapters(client):
    headers = await _auth(client)
    resp = await client.get(
        "/api/v1/models/estimate?model_id=anthropic/claude-3.5-sonnet&chapters=100",
        headers=headers,
    )
    assert resp.status_code == 422
