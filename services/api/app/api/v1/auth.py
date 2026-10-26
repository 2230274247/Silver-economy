import secrets
from datetime import UTC, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import (
    COOKIE_NAME,
    CurrentUser,
    DatabaseSession,
    dummy_hash,
    hash_token,
    utc_now,
    verify_password,
)
from app.models.entities import AuthSession, User

router = APIRouter(prefix="/api/v1")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login_name: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


def user_data(user: User):
    return {"id": user.id, "login_name": user.login_name}


@router.post("/auth/login")
def login(payload: Login, request: Request, response: Response, db: DatabaseSession):
    user = db.scalar(select(User).where(User.login_name == payload.login_name))
    valid = verify_password(
        payload.password.get_secret_value(), user.password_hash if user else dummy_hash
    )
    if (
        not valid
        or user is None
        or user.disabled_at is not None
        or (get_settings().ui_test_mode and user.login_name not in {"ui_a", "ui_b"})
    ):
        raise ApiError(401, "INVALID_CREDENTIALS", "账号或密码不正确")
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == hash_token(old_token))
            .values(revoked_at=utc_now())
        )
    token = secrets.token_urlsafe(32)
    expires = utc_now() + timedelta(seconds=get_settings().session_ttl_seconds)
    db.add(AuthSession(user_id=user.id, token_hash=hash_token(token), expires_at=expires))
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=get_settings().session_ttl_seconds,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/api",
    )
    return {"user": user_data(user), "expires_at": expires.replace(tzinfo=UTC).isoformat()}


@router.get("/me")
def me(user: CurrentUser):
    return user_data(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DatabaseSession):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == hash_token(token))
            .values(revoked_at=utc_now())
        )
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api", httponly=True, samesite="lax")
