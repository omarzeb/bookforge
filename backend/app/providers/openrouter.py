"""
OpenRouter provider implementation.

Uses the openai SDK pointed at openrouter.ai.
Required headers:
  HTTP-Referer — identifies your app in OpenRouter's dashboard
  X-Title      — human-readable app name shown in their UI
"""

from collections.abc import AsyncGenerator

import structlog
from openai import AsyncOpenAI
from openai import APIConnectionError, APIStatusError

from app.providers.base import GenerateResult, LLMProvider, ModelInfo
from app.providers.exceptions import (
    ContextTooLong,
    InvalidKey,
    ModelNotFound,
    OutOfCredits,
    ProviderUnavailable,
    RateLimited,
)

logger = structlog.get_logger(__name__)

_BASE_URL = "https://openrouter.ai/api/v1"
_REFERER = "https://github.com/bookforge"
_TITLE = "BookForge"


def _make_client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=_BASE_URL,
        default_headers={
            "HTTP-Referer": _REFERER,
            "X-Title": _TITLE,
        },
    )


def _map_error(exc: APIStatusError) -> Exception:
    """Map OpenRouter HTTP status codes to domain exceptions."""
    code = exc.status_code
    msg = str(exc.message) if hasattr(exc, "message") else str(exc)

    if code == 401:
        return InvalidKey(f"OpenRouter rejected the API key: {msg}")
    if code == 402:
        return OutOfCredits("OpenRouter account has insufficient credits")
    if code == 429:
        return RateLimited(f"Rate limited by OpenRouter: {msg}")
    if code == 400 and "context" in msg.lower():
        return ContextTooLong(f"Prompt exceeds model context window: {msg}")
    if code == 404:
        return ModelNotFound(f"Model not found on OpenRouter: {msg}")
    if code >= 500:
        return ProviderUnavailable(f"OpenRouter server error {code}: {msg}")
    return ProviderUnavailable(f"Unexpected OpenRouter error {code}: {msg}")


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
    ) -> GenerateResult:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except APIStatusError as exc:
            raise _map_error(exc) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailable(f"Could not reach OpenRouter: {exc}") from exc

        choice = response.choices[0]
        usage = response.usage

        return GenerateResult(
            content=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
        )

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
                    {"role": "user", "content": user},
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
        # Rough estimate: ~4 chars per token (good enough for cost previews)
        return max(1, len(text) // 4)

    async def list_models(self) -> list[ModelInfo]:
        """
        Fetch the live model list from OpenRouter's /models endpoint.
        Returns a flat list — the caller assigns tier labels.
        """
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_BASE_URL}/models",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "HTTP-Referer": _REFERER,
                        "X-Title": _TITLE,
                    },
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
                prompt_price = float(pricing.get("prompt", 0)) * 1000
                completion_price = float(pricing.get("completion", 0)) * 1000
            except (TypeError, ValueError):
                prompt_price = None
                completion_price = None

            models.append(ModelInfo(
                model_id=m.get("id", ""),
                name=m.get("name", m.get("id", "")),
                context_length=m.get("context_length"),
                prompt_price_per_1k=prompt_price,
                completion_price_per_1k=completion_price,
                tier=None,  # assigned by model sync service
            ))

        return models

    async def validate_key(self) -> bool:
        """
        Make a minimal generation call to verify the key works.
        Raises InvalidKey or OutOfCredits on failure.
        """
        await self.generate(
            model="openai/gpt-4o-mini",
            system="You are a test assistant.",
            user="Reply with the single word: ok",
            max_tokens=5,
            temperature=0.0,
        )
        return True
