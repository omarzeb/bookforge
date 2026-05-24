"""
JWT authentication and password hashing.

Password hashing: HMAC-SHA256(pepper, password) → bcrypt
The pepper is APP_SECRET_KEY — a leaked DB hash cannot be validated
without also knowing the pepper.

JWT: PyJWT with HS256, includes iat + jti + iss + aud.
"""

import hmac as _hmac
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt as pyjwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.session import get_db

logger = structlog.get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Pre-computed dummy hash for constant-time comparison when user not found
_DUMMY_HASH = bcrypt.hashpw(b"dummy-constant-time-comparison", bcrypt.gensalt()).decode()


def _pepper(raw: str) -> bytes:
    """Apply server-side HMAC-SHA256 pepper before bcrypt."""
    pepper = settings.app_secret_key.encode()
    return _hmac.new(pepper, raw.encode(), "sha256").hexdigest().encode()


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_pepper(raw), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(_pepper(raw), hashed.encode())


def verify_password_constant_time(raw: str, hashed: str | None) -> bool:
    """Always runs bcrypt — prevents timing-based user enumeration."""
    check_hash = hashed if hashed else _DUMMY_HASH
    result = bcrypt.checkpw(_pepper(raw), check_hash.encode())
    return result and hashed is not None


def create_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "iss": "bookforge",
        "aud": "bookforge-api",
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = pyjwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="bookforge-api",
            issuer="bookforge",
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except pyjwt.PyJWTError as exc:
        raise credentials_exc from exc

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exc
    return user
