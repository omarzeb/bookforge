"""
Provider factory.

get_provider_for_user() is the single entry point for getting a configured
provider. It decrypts the user's stored API key, instantiates the provider,
and returns it. The decrypted key is never stored — it lives only in memory
for the duration of the request.
"""

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings
from app.db.models import User
from app.providers.base import LLMProvider
from app.providers.exceptions import InvalidKey
from app.providers.openrouter import OpenRouterProvider

logger = structlog.get_logger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt_api_key(raw_key: str) -> str:
    """Encrypt a plaintext API key for storage. Returns a base64 string."""
    return _get_fernet().encrypt(raw_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt a stored API key.
    Raises InvalidKey if the token is malformed or the Fernet key has changed.
    """
    try:
        return _get_fernet().decrypt(encrypted_key.encode()).decode()
    except (InvalidToken, Exception) as exc:
        raise InvalidKey("Could not decrypt stored API key — it may be corrupted") from exc


def get_provider_for_user(user: User) -> LLMProvider:
    """
    Return a configured LLM provider for the given user.

    In DEMO_MODE, returns a provider backed by the demo key from config.
    Otherwise, decrypts the user's stored key and returns their provider.

    Raises InvalidKey if the user has no key saved.
    """
    if settings.demo_mode and settings.openrouter_demo_key:
        logger.debug("using_demo_key", user_id=user.id)
        return OpenRouterProvider(api_key=settings.openrouter_demo_key)

    if not user.encrypted_api_key:
        raise InvalidKey(
            "No OpenRouter API key saved. "
            "Go to Settings and add your key to start generating."
        )

    raw_key = decrypt_api_key(user.encrypted_api_key)
    return OpenRouterProvider(api_key=raw_key)
