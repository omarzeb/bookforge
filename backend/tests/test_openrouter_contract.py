"""
Contract tests against real OpenRouter API.

These are gated behind OPENROUTER_CONTRACT_TESTS=true so they never run in CI
and never burn tokens automatically. Run locally when you change provider code:

    OPENROUTER_CONTRACT_TESTS=true pytest tests/test_openrouter_contract.py -v
"""

import os

import pytest

from app.providers.openrouter import OpenRouterProvider

SKIP = not os.getenv("OPENROUTER_CONTRACT_TESTS")


@pytest.mark.skipif(SKIP, reason="Set OPENROUTER_CONTRACT_TESTS=true to run")
@pytest.mark.asyncio
async def test_validate_key_real():
    key = os.environ["OPENROUTER_DEMO_KEY"]
    provider = OpenRouterProvider(api_key=key)
    result = await provider.validate_key()
    assert result is True


@pytest.mark.skipif(SKIP, reason="Set OPENROUTER_CONTRACT_TESTS=true to run")
@pytest.mark.asyncio
async def test_generate_real():
    key = os.environ["OPENROUTER_DEMO_KEY"]
    provider = OpenRouterProvider(api_key=key)
    result = await provider.generate(
        model="openai/gpt-4o-mini",
        system="You are a test assistant. Be concise.",
        user="Reply with the single word: ok",
        max_tokens=10,
        temperature=0.0,
    )
    assert "ok" in result.content.lower()
    assert result.prompt_tokens > 0


@pytest.mark.skipif(SKIP, reason="Set OPENROUTER_CONTRACT_TESTS=true to run")
@pytest.mark.asyncio
async def test_list_models_real():
    key = os.environ["OPENROUTER_DEMO_KEY"]
    provider = OpenRouterProvider(api_key=key)
    models = await provider.list_models()
    assert len(models) > 10
    ids = [m.model_id for m in models]
    assert any("gpt" in mid for mid in ids)
