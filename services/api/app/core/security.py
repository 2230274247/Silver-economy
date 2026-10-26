import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.errors import ApiError
from app.models.entities import AuthSession, User

hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
DatabaseSession = Annotated[Session, Depends(get_session)]
COOKIE_NAME = "silver_session"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except VerificationError:
        return False


def current_user(request: Request, db: DatabaseSession) -> User:
    value = request.cookies.get(COOKIE_NAME, "")
    if len(value) < 32 or len(value) > 128:
        raise ApiError(401, "AUTH_REQUIRED", "请先登录")
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == hash_token(value),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
            User.disabled_at.is_(None),
        )
    )
    if user is None:
        raise ApiError(401, "AUTH_REQUIRED", "登录已失效，请重新登录")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
