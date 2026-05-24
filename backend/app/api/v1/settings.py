"""
User settings routes.

PUT /settings/openrouter-key
  Validates the key with a real test call before encrypting and saving it.
  Never stores the raw key — only the Fernet-encrypted version.

GET /settings/openrouter-key
  Returns whether a key is saved (not the key itself).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.providers.exceptions import InvalidKey, OutOfCredits
from app.providers.factory import encrypt_api_key
from app.providers.openrouter import OpenRouterProvider

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


from app.core.auth import get_current_user


class SaveKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10, description="OpenRouter API key (sk-or-...)")


class KeyStatusResponse(BaseModel):
    has_key: bool


@router.put("/openrouter-key", status_code=204)
async def save_openrouter_key(
    body: SaveKeyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """
    Validate the key with a live test call, then encrypt and save it.
    Returns 204 on success, 422 if the key is invalid, 402 if out of credits.
    """
    provider = OpenRouterProvider(api_key=body.api_key)

    try:
        await provider.validate_key()
    except InvalidKey as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OutOfCredits as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    user.encrypted_api_key = encrypt_api_key(body.api_key)
    db.add(user)
    await db.commit()

    logger.info("api_key_saved", user_id=user.id)


@router.get("/openrouter-key", response_model=KeyStatusResponse)
async def get_key_status(
    user: User = Depends(get_current_user),
) -> KeyStatusResponse:
    """Returns whether the user has a saved OpenRouter key (not the key itself)."""
    return KeyStatusResponse(has_key=bool(user.encrypted_api_key))


@router.delete("/openrouter-key", status_code=204)
async def delete_openrouter_key(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Remove the stored OpenRouter API key."""
    user.encrypted_api_key = None
    db.add(user)
    await db.commit()
    logger.info("api_key_deleted", user_id=user.id)
