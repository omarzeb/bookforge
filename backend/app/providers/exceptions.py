from app.core.exception_handlers import ProviderError


class InvalidKey(ProviderError):
    """API key is missing, malformed, or rejected by the provider."""


class OutOfCredits(ProviderError):
    """User's OpenRouter account has no remaining credits."""


class RateLimited(ProviderError):
    """Provider is rate-limiting this key — back off and retry."""


class ProviderUnavailable(ProviderError):
    """Provider returned a 5xx or is unreachable."""


class ContextTooLong(ProviderError):
    """Prompt exceeds the model's context window."""


class ModelNotFound(ProviderError):
    """Requested model ID does not exist or is not accessible."""
