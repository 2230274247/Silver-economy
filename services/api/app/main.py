import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.errors import ApiError

app = FastAPI(title="银发记忆 Demo", version="0.1.0-alpha")
silver_logger = logging.getLogger("silver")
silver_logger.setLevel(logging.INFO)
silver_logger.propagate = False
if not silver_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s UTC %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    silver_logger.addHandler(handler)
logger = logging.getLogger("silver.api")
app.include_router(auth_router)
app.include_router(chat_router)


@app.middleware("http")
async def request_metadata(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    origin = request.headers.get("origin")
    if (
        request.method not in {"GET", "HEAD", "OPTIONS"}
        and origin
        and origin
        not in {
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:5174",
        }
    ):
        response = error_response(request, 403, "ORIGIN_DENIED", "请求来源不允许")
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "request_id=%s method=%s status=%s latency_ms=%s",
        request.state.request_id,
        request.method,
        response.status_code,
        int((time.monotonic() - start) * 1000),
    )
    return response


def error_response(request: Request, status: int, code: str, message: str):
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "request_id": request.state.request_id}
        },
    )


@app.exception_handler(ApiError)
async def api_error(request: Request, exc: ApiError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, f"HTTP_{exc.status_code}", "请求未完成")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "VALIDATION_ERROR", "请检查提交内容的格式")


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    return error_response(request, 503, "DATABASE_UNAVAILABLE", "数据服务暂不可用，请稍后重试")


@app.get("/")
def index() -> dict[str, str]:
    return {
        "service": "silver-memory-api",
        "stage": "chat",
        "provider": get_settings().llm_provider,
    }


@app.get("/api/v1/model-status")
def model_status():
    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "configured": settings.llm_provider == "mock"
        or bool(settings.deepseek_api_key.get_secret_value().strip()),
    }


@app.get("/api/v1/healthz")
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/api/v1/readyz")
def readiness():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        return {"status": "ready", "schema_revision": revision}
    except (SQLAlchemyError, ValueError):
        raise ApiError(
            503, "DATABASE_UNAVAILABLE", "数据服务暂不可用，请检查本项目数据库及迁移"
        ) from None
