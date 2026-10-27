"""Owned queries with durable idempotency, bounded caching and shared Amap budget."""

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import utc_now
from app.maps.providers import MapFailure, get_maps_provider
from app.models.entities import MapBudget, MapRequest
from app.tasks.repository import draft_data, missing_fields, owned_draft, stamp
from app.tasks.time_parse import ZONE

ERRORS = {
    "MAP_NOT_CONFIGURED": "地图天气服务尚未配置；可继续保存信息，不能宣称已查询",
    "MAP_BUDGET_EXCEEDED": "今日地图查询额度已用完，请稍后再查",
    "MAP_TIMEOUT": "地图查询超时，结果不确定，不自动重发",
    "MAP_NETWORK_UNKNOWN": "地图连接异常，结果不确定，不自动重发",
    "MAP_RESPONSE_FORMAT": "地图响应无法可靠解析，请核对服务配置",
    "MAP_PROVIDER_ERROR": "地图服务拒绝请求或暂不可用，请管理员核对权限和配额",
    "MAP_NO_ROUTE": "没有可用路线，可在后续选择普通时间提醒",
    "MAP_CITY_REQUIRED": "公交查询缺少城市编码，请选择更具体的地点",
}


def checked_draft(db, user_id, draft_id, revision, *, consent=True, allow_deferred=False):
    draft = owned_draft(db, user_id, draft_id, lock=True)
    if draft.status in {"scheduled", "cancelled", "completed"}:
        raise ApiError(409, "TASK_DRAFT_ALREADY_SCHEDULED", "此草案已进入任务流程")
    if draft.revision != revision:
        raise ApiError(409, "TASK_DRAFT_STALE", "草案已更新，请重新读取后核对")
    if draft.kind != "outing" or draft.status == "deferred" and not allow_deferred:
        raise ApiError(409, "MAP_DRAFT_UNAVAILABLE", "此草案不能查询出行路线")
    if consent and not draft.location_consent:
        raise ApiError(403, "LOCATION_CONSENT_REQUIRED", "请先明确同意本次行程的位置查询用途")
    return draft


def changed(draft):
    draft.revision += 1
    draft.map_snapshot = None
    if draft.status != "deferred":
        draft.status, draft.confirmed_at = "draft", None


def consent(db, user_id, draft_id, payload):
    draft = checked_draft(
        db,
        user_id,
        draft_id,
        payload.expected_revision,
        consent=False,
        allow_deferred=not payload.enabled,
    )
    if draft.location_consent != payload.enabled:
        draft.location_consent = payload.enabled
        changed(draft)
    if not payload.enabled:
        draft.origin_place = draft.destination_place = draft.map_snapshot = None
        # Withdrawn results cannot be replayed, selected or returned from a hidden cache.
        db.execute(
            update(MapRequest)
            .where(MapRequest.user_id == user_id, MapRequest.draft_id == draft_id)
            .values(result=None, status="revoked", context={})
        )
    db.commit()
    return draft_data(draft)


def query(db, draft, client_key, operation, parameters, context, invoke, *, expected_revision=None):
    revision = draft.revision if expected_revision is None else expected_revision
    # Each external stage reacquires the owner lock after the previous durable receipt committed.
    draft = checked_draft(db, draft.user_id, draft.id, revision)
    settings = get_settings()
    provider = get_maps_provider(settings)
    fingerprint = hashlib.sha256(
        json.dumps(
            [provider.name, parameters, context], ensure_ascii=False, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = db.scalar(
        select(MapRequest).where(
            MapRequest.user_id == draft.user_id,
            MapRequest.client_request_id == str(client_key),
            MapRequest.operation == operation,
        )
    )
    if existing:
        if existing.fingerprint != fingerprint or existing.draft_id != draft.id:
            raise ApiError(409, "MAP_REQUEST_CONFLICT", "请求编号已用于其他查询，请重新核对信息")
        if existing.status != "completed" or existing.result is None:
            raise MapFailure(existing.error_code or "MAP_NETWORK_UNKNOWN")
        return existing
    now = utc_now()
    cached = db.scalar(
        select(MapRequest)
        .where(
            MapRequest.user_id == draft.user_id,
            MapRequest.draft_id == draft.id,
            MapRequest.operation == operation,
            MapRequest.fingerprint == fingerprint,
            MapRequest.expires_at > now,
            MapRequest.status.in_(["reserved", "completed", "failed", "unknown"]),
        )
        .order_by(MapRequest.created_at.desc(), MapRequest.id.desc())
        .limit(1)
    )
    if cached and cached.status != "completed":
        raise MapFailure(cached.error_code or "MAP_NETWORK_UNKNOWN")
    if not cached and provider.name == "amap":
        day = datetime.now(ZONE).date().isoformat()
        db.execute(insert(MapBudget).values(day=day, requests=0).on_duplicate_key_update(day=day))
        budget = db.scalar(select(MapBudget).where(MapBudget.day == day).with_for_update())
        if budget.requests >= settings.amap_daily_request_limit:
            raise MapFailure("MAP_BUDGET_EXCEEDED")
        budget.requests += 1
    record = MapRequest(
        user_id=draft.user_id,
        draft_id=draft.id,
        client_request_id=str(client_key),
        operation=operation,
        provider=provider.name,
        fingerprint=fingerprint,
        status="completed" if cached else "reserved",
        context=context,
        result=cached.result if cached else None,
        expires_at=cached.expires_at if cached else now + timedelta(minutes=15),
    )
    db.add(record)
    db.commit()  # Quota/intent durable before any external I/O. Never blindly retry reserved calls.
    if cached:
        return record
    started = time.monotonic()
    try:
        result = invoke(provider)
        current = owned_draft(db, draft.user_id, draft.id, lock=True)
        if (
            not current.location_consent
            or current.revision != revision
            or current.status == "deferred"
        ):
            record.status, record.error_code = "rejected", "MAP_DRAFT_CHANGED"
            raise ApiError(409, "MAP_DRAFT_CHANGED", "查询期间草案或位置授权已改变，请重新核对")
        record.result = {
            **result,
            "provider": provider.name,
            "is_synthetic": provider.name == "mock",
            "fetched_at": stamp(utc_now()),
            "expires_at": stamp(record.expires_at),
        }
        record.status = "completed"
    except MapFailure as failure:
        record.status = (
            "unknown" if failure.code in {"MAP_TIMEOUT", "MAP_NETWORK_UNKNOWN"} else "failed"
        )
        record.error_code = failure.code
        raise
    finally:
        record.latency_ms = int((time.monotonic() - started) * 1000)
        db.commit()
    return record


def search(db, user_id, draft_id, payload):
    draft = checked_draft(db, user_id, draft_id, payload.expected_revision)
    parameters = payload.model_dump(mode="json", exclude={"expected_revision", "client_request_id"})
    context = {"field": payload.field, "label": getattr(draft, payload.field)}
    try:
        record = query(
            db,
            draft,
            payload.client_request_id,
            "search",
            parameters,
            context,
            lambda provider: provider.search(payload.query, payload.city, payload.search_kind),
        )
    except MapFailure as failure:
        raise ApiError(503, failure.code, ERRORS.get(failure.code, "位置查询未完成")) from None
    return {"query_id": record.id, **record.result}


def select_place(db, user_id, draft_id, payload):
    draft = checked_draft(db, user_id, draft_id, payload.expected_revision)
    record = db.scalar(
        select(MapRequest).where(
            MapRequest.user_id == user_id,
            MapRequest.draft_id == draft_id,
            MapRequest.id == str(payload.query_id),
            MapRequest.operation == "search",
        )
    )
    if record is None:
        raise ApiError(404, "NOT_FOUND", "地点查询不存在或无法访问")
    if record.provider != get_settings().maps_provider:
        raise ApiError(409, "MAP_PROVIDER_CHANGED", "查询模式已改变，请重新搜索地点")
    if (
        record.status != "completed"
        or not record.result
        or record.expires_at <= utc_now()
        or record.context != {"field": payload.field, "label": getattr(draft, payload.field)}
    ):
        raise ApiError(
            409, "MAP_SELECTION_EXPIRED", "候选已过期、位置授权或地点文字已改变，请重新搜索"
        )
    place = next((p for p in record.result["items"] if p["id"] == str(payload.candidate_id)), None)
    if place is None:
        raise ApiError(404, "NOT_FOUND", "候选不存在或无法访问")
    selected = {
        **place,
        "provider": record.provider,
        "is_synthetic": record.provider == "mock",
        "fetched_at": record.result["fetched_at"],
    }
    setattr(draft, payload.field + "_place", selected)
    setattr(draft, payload.field, place["name"])
    draft.evidence = {
        **draft.evidence,
        payload.field: {
            "origin": "user_place_selection",
            "value": place["name"],
            "at": stamp(utc_now()),
        },
    }
    changed(draft)
    db.commit()
    return draft_data(draft)


def preview(db, user_id, draft_id, payload):
    draft = checked_draft(db, user_id, draft_id, payload.expected_revision)
    if missing_fields(draft) or not draft.origin_place or not draft.destination_place:
        raise ApiError(
            422, "MAP_PLACES_REQUIRED", "请补全时间、到达/出发、交通方式，并明确选择两个地点"
        )
    settings = get_settings()
    if any(
        p["provider"] != settings.maps_provider
        for p in (draft.origin_place, draft.destination_place)
    ):
        raise ApiError(409, "MAP_PROVIDER_CHANGED", "查询模式已改变，请用当前服务重新选择地点")
    revision = draft.revision
    origin, destination, mode = draft.origin_place, draft.destination_place, draft.transport
    if mode == "transit" and (not origin["citycode"] or not destination["citycode"]):
        raise ApiError(422, "MAP_CITY_REQUIRED", ERRORS["MAP_CITY_REQUIRED"])
    day = draft.target_at.replace(tzinfo=UTC).astimezone(ZONE).date().isoformat()
    try:
        route = query(
            db,
            draft,
            payload.client_request_id,
            "route",
            {
                "origin": {k: origin[k] for k in ("location", "citycode")},
                "destination": {k: destination[k] for k in ("location", "citycode")},
                "mode": mode,
            },
            {},
            lambda provider: provider.route(origin, destination, mode),
            expected_revision=revision,
        ).result
    except MapFailure as failure:
        route = {
            "status": "unavailable",
            "reason": failure.code,
            "message": ERRORS.get(failure.code, "路线查询未完成"),
        }
    if route.get("duration_seconds"):
        try:
            weather = query(
                db,
                draft,
                payload.client_request_id,
                "weather",
                {"adcode": destination["adcode"], "day": day},
                {},
                lambda provider: provider.weather(destination, day),
                expected_revision=revision,
            ).result
        except MapFailure as failure:
            weather = {"status": "unavailable", "reason": failure.code}
    else:
        weather = {"status": "unavailable", "reason": "ROUTE_UNAVAILABLE_NOT_QUERIED"}
    draft = checked_draft(db, user_id, draft_id, revision)
    draft.map_snapshot = {
        "draft_revision": revision,
        "provider": settings.maps_provider,
        "is_synthetic": settings.maps_provider == "mock",
        "route": route,
        "weather": weather,
        "expires_at": route.get("expires_at", stamp(utc_now())),
        "scheduling_status": "not_scheduled",
    }
    db.commit()
    return draft_data(draft)
