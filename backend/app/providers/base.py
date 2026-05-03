"""
LLM provider abstract base class.

Every provider must implement this interface.
Keeps the rest of the codebase provider-agnostic.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class ModelInfo:
    model_id: str
    name: str
    context_length: int | None
    prompt_price_per_1k: float | None
    completion_price_per_1k: float | None
    tier: str | None  # Recommended / Budget / Premium / Other


@dataclass
class GenerateResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    model: str  # actual model used (may differ if provider does routing)


class LLMProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> GenerateResult:
        """Single-turn generation — returns full response once complete."""

    @abstractmethod
    async def stream(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Streaming generation — yields token chunks as they arrive."""

    @abstractmethod
    async def estimate_tokens(self, text: str) -> int:
        """Rough token count for cost estimation before generation."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Fetch available models from the provider."""

    @abstractmethod
    async def validate_key(self) -> bool:
        """
        Verify the key is valid and has credits.
        Raises InvalidKey or OutOfCredits on failure.
        """
