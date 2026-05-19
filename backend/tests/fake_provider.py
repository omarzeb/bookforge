"""
Fake LLM provider for unit tests.

Returns predictable responses without making real API calls.
Swap in via dependency override in conftest.py.
"""

from collections.abc import AsyncGenerator

from app.providers.base import GenerateResult, LLMProvider, ModelInfo

FAKE_MODELS = [
    ModelInfo(
        model_id="fake/fast",
        name="Fake Fast Model",
        context_length=8192,
        prompt_price_per_1k=0.001,
        completion_price_per_1k=0.002,
        tier="Budget",
    ),
    ModelInfo(
        model_id="fake/smart",
        name="Fake Smart Model",
        context_length=32768,
        prompt_price_per_1k=0.01,
        completion_price_per_1k=0.03,
        tier="Recommended",
    ),
]


class FakeLLMProvider(LLMProvider):
    """
    Deterministic fake provider. Configurable response for testing.
    """

    def __init__(self, response: str = "fake response") -> None:
        self._response = response
        self.calls: list[dict] = []  # records all generate() calls for assertions

    async def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        user_id: str | None = None,
        book_id: str | None = None,
        stage: str = "unknown",
        db=None,
    ) -> GenerateResult:
        self.calls.append({"model": model, "system": system, "user": user})
        return GenerateResult(
            content=self._response,
            prompt_tokens=len(user) // 4,
            completion_tokens=len(self._response) // 4,
            model=model,
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
        async def _gen():
            for word in self._response.split():
                yield word + " "
        return _gen()

    async def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def list_models(self) -> list[ModelInfo]:
        return FAKE_MODELS

    async def validate_key(self) -> bool:
        return True
