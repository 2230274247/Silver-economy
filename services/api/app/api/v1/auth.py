import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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
from app.models.entities import AdminModelBudget, AuthSession, User

router = APIRouter(prefix="/api/v1")


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    login_name: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


def user_data(user: User):
    return {"id": user.id, "login_name": user.login_name, "is_admin": user.is_admin}


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


@router.get("/admin/model-status")
def admin_status(user: CurrentUser, db: DatabaseSession):
    if not user.is_admin:
        raise ApiError(403, "ADMIN_REQUIRED", "此页面仅供管理员使用")
    settings = get_settings()
    day = datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
    budget = db.get(AdminModelBudget, day)
    return {
        "model": settings.deepseek_model,
        "provider": settings.llm_provider,
        "search_enabled": settings.deepseek_search_enabled,
        "daily_request_limit": settings.admin_daily_request_limit,
        "daily_token_limit": settings.admin_daily_token_limit,
        "max_output_tokens": settings.admin_max_output_tokens,
        "requests_used": budget.requests if budget else 0,
        "reserved_tokens": budget.reserved_tokens if budget else 0,
        "budget_scope": "administrator_pool",
    }


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
