"""
Provider unit tests — no real API calls.
"""

import pytest

from app.providers.base import GenerateResult
from tests.fake_provider import FakeLLMProvider


@pytest.mark.asyncio
async def test_fake_provider_generate():
    provider = FakeLLMProvider(response="chapter content here")
    result = await provider.generate(
        model="fake/fast",
        system="You are a writer.",
        user="Write chapter 1.",
    )
    assert isinstance(result, GenerateResult)
    assert result.content == "chapter content here"
    assert result.model == "fake/fast"
    assert result.prompt_tokens > 0


@pytest.mark.asyncio
async def test_fake_provider_stream():
    provider = FakeLLMProvider(response="hello world foo")
    chunks = []
    gen = await provider.stream(
        model="fake/fast",
        system="sys",
        user="user",
    )
    async for chunk in gen:
        chunks.append(chunk)
    assert "".join(chunks).strip() == "hello world foo"


@pytest.mark.asyncio
async def test_fake_provider_records_calls():
    provider = FakeLLMProvider()
    await provider.generate(model="fake/fast", system="sys", user="msg1")
    await provider.generate(model="fake/fast", system="sys", user="msg2")
    assert len(provider.calls) == 2
    assert provider.calls[0]["user"] == "msg1"


@pytest.mark.asyncio
async def test_fake_provider_validate_key():
    provider = FakeLLMProvider()
    result = await provider.validate_key()
    assert result is True


@pytest.mark.asyncio
async def test_fake_provider_list_models():
    provider = FakeLLMProvider()
    models = await provider.list_models()
    assert len(models) > 0
    assert any(m.tier == "Recommended" for m in models)
