"""
OpenRouter provider — instrumented with usage logging and Sentry.
"""

from collections.abc import AsyncGenerator
import time

import structlog
from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from app.providers.base import GenerateResult, LLMProvider, ModelInfo
from app.providers.exceptions import (
    ContextTooLong, InvalidKey, ModelNotFound,
    OutOfCredits, ProviderUnavailable, RateLimited,
)

logger = structlog.get_logger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"
_REFERER = "https://github.com/bookforge"
_TITLE = "BookForge"


def _make_client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=_BASE_URL,
        default_headers={"HTTP-Referer": _REFERER, "X-Title": _TITLE},
    )


def _map_error(exc: APIStatusError) -> Exception:
    code = exc.status_code
    msg = str(exc.message) if hasattr(exc, "message") else str(exc)
    if code == 401: return InvalidKey(f"OpenRouter rejected the API key: {msg}")
    if code == 402: return OutOfCredits("OpenRouter account has insufficient credits")
    if code == 429: return RateLimited(f"Rate limited by OpenRouter: {msg}")
    if code == 400 and "context" in msg.lower(): return ContextTooLong(f"Prompt exceeds context window: {msg}")
    if code == 404: return ModelNotFound(f"Model not found: {msg}")
    if code >= 500: return ProviderUnavailable(f"OpenRouter server error {code}: {msg}")
    return ProviderUnavailable(f"Unexpected error {code}: {msg}")


def _estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Rough cost estimate. Real pricing comes from ModelCache.
    Used as a fallback when cache isn't available.
    """
    # Conservative defaults — actual cost may differ
    DEFAULTS = {
        "prompt_per_1k":     0.001,
        "completion_per_1k": 0.002,
    }
    return (
        (prompt_tokens / 1000) * DEFAULTS["prompt_per_1k"]
        + (completion_tokens / 1000) * DEFAULTS["completion_per_1k"]
    )


class OpenRouterProvider(LLMProvider):

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = _make_client(api_key)

    async def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        # Optional usage logging context — set by callers
        user_id: str | None = None,
        book_id: str | None = None,
        stage: str = "unknown",
        db=None,
    ) -> GenerateResult:
        start = time.time()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except APIStatusError as exc:
            raise _map_error(exc) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailable(f"Could not reach OpenRouter: {exc}") from exc

        duration_ms = int((time.time() - start) * 1000)
        choice = response.choices[0]
        usage  = response.usage

        result = GenerateResult(
            content=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
        )

        # Log usage if context provided
        if db and user_id:
            try:
                from app.services.usage_service import log_usage
                from app.db.models import ModelCache
                from sqlalchemy import select

                # Try to get real pricing from cache
                cache_result = await db.execute(
                    select(ModelCache).where(ModelCache.model_id == model)
                )
                cached = cache_result.scalar_one_or_none()

                if cached and cached.prompt_price_per_1k and cached.completion_price_per_1k:
                    cost = (
                        (result.prompt_tokens / 1000) * cached.prompt_price_per_1k
                        + (result.completion_tokens / 1000) * cached.completion_price_per_1k
                    )
                else:
                    cost = _estimate_cost(model, result.prompt_tokens, result.completion_tokens)

                await log_usage(
                    db,
                    user_id=user_id,
                    book_id=book_id,
                    model=model,
                    stage=stage,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    cost_usd=cost,
                    duration_ms=duration_ms,
                )
            except Exception as log_exc:
                logger.warning("usage_log_failed", error=str(log_exc))

        logger.debug(
            "llm_generate",
            model=model,
            stage=stage,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            duration_ms=duration_ms,
        )
        return result

    async def stream(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        try:
            async with self._client.chat.completions.stream(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta
        except APIStatusError as exc:
            raise _map_error(exc) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailable(f"Could not reach OpenRouter: {exc}") from exc

    async def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def list_models(self) -> list[ModelInfo]:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self._api_key}", "HTTP-Referer": _REFERER, "X-Title": _TITLE},
                    timeout=15.0,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderUnavailable(f"Failed to fetch models: {exc}") from exc

        models: list[ModelInfo] = []
        for m in data.get("data", []):
            pricing = m.get("pricing", {})
            try:
                prompt_price      = float(pricing.get("prompt", 0)) * 1000
                completion_price  = float(pricing.get("completion", 0)) * 1000
            except (TypeError, ValueError):
                prompt_price = completion_price = None
            models.append(ModelInfo(
                model_id=m.get("id", ""),
                name=m.get("name", m.get("id", "")),
                context_length=m.get("context_length"),
                prompt_price_per_1k=prompt_price,
                completion_price_per_1k=completion_price,
                tier=None,
            ))
        return models

    async def validate_key(self) -> bool:
        await self.generate(
            model="openai/gpt-4o-mini",
            system="You are a test assistant.",
            user="Reply with the single word: ok",
            max_tokens=5,
            temperature=0.0,
        )
        return True
