"""Bounded official DeepSeek search, without sending private memory to search."""

import json
import re
import time
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.llm.providers import ProviderFailure
from app.models.entities import ModelUsage

WEB_CONTEXT_LIMIT = 2200
WEB_MARKER = "CHAT_WEATHER_CONTEXT_PENDING"


def weather_plan(text):
    if not re.search(r"天气|气温|下雨|降雨|带伞", text) or len(text) > 256:
        return None
    # Only an explicitly named place from the current message is searched.
    match = re.search(r"([\u4e00-\u9fff]{2,16}?)(?:的)?(?:天气|气温|下雨|降雨)", text)
    place = match[1] if match else ""
    place = re.sub(
        r"^(?:请问|请|帮我|查一下|查询|查查|告诉我|今天|明天|后天|现在|想知道|我想知道)+", "", place
    )
    place = place.rstrip("的")
    place = re.sub(r"今天|明天|后天|现在", "", place).rstrip("的")
    now = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    offset = 2 if "后天" in text else 1 if "明天" in text else 0
    day = (now + timedelta(days=offset)).date().isoformat()
    if (
        place in {"这里", "当地", "那边", "这边", "我家", "我们这", "今日", "最近"}
        or len(place) < 2
        or re.search(r"小区|街|路|号|住在|住址|单元|室|楼|我家|公司", place)
    ):
        return {
            "status": "missing_location",
            "date": day,
            "message": "还缺城市，请自然询问用户想查询哪个城市。",
        }
    return {
        "status": "pending",
        "city": place,
        "date": day,
        "query": f"{place} {day} 天气预报 中国天气网 气象台",
    }


def search_weather(db, item, assistant, settings, plan, reserve):
    if plan["status"] != "pending":
        return plan
    if assistant.search_context:
        return assistant.search_context
    if settings.llm_provider != "deepseek":
        return {**plan, "status": "unavailable", "message": "Mock测试没有实时天气，不可编造实况。"}
    if not settings.deepseek_search_enabled:
        return {**plan, "status": "disabled", "message": "联网查询已关闭，没有实时天气依据。"}
    existing = db.scalar(
        select(ModelUsage).where(
            ModelUsage.user_id == item.user_id,
            ModelUsage.request_id == item.client_request_id,
            ModelUsage.purpose == "weather_search",
        )
    )
    if existing:
        return {**plan, "status": "unknown", "message": "先前联网查询结果未确认，不自动重复查询。"}
    try:
        reserve(db, settings, 0)
    except ProviderFailure:
        return {
            **plan,
            "status": "budget_exceeded",
            "message": "本次联网查询额度不足，没有实时天气依据。",
        }
    usage = ModelUsage(
        user_id=item.user_id,
        provider="deepseek",
        model="search-api",
        purpose="weather_search",
        request_id=item.client_request_id,
        prompt_version="weather-search/v1",
        status="reserved",
        reserved_tokens=0,
    )
    db.add(usage)
    assistant.search_context = {**plan, "status": "reserved"}
    db.commit()
    started = time.monotonic()
    context = {**plan, "queried_at": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat()}
    try:
        with httpx.Client(
            timeout=httpx.Timeout(12, connect=5), follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(
                "https://api.deepseek.com/v1/tools/search",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key.get_secret_value()}"},
                json={"query": plan["query"][:128], "count": 3, "need_content": False},
            )
        if response.status_code != 200:
            raise ProviderFailure(f"SEARCH_HTTP_{response.status_code}")
        rows = response.json()["results"]
        if not isinstance(rows, list):
            raise ValueError("Invalid search results")
        results = []
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url", ""))
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                continue
            entry = {
                "title": str(row.get("title", ""))[:100],
                "url": url[:350],
                "summary": str(row.get("summary") or row.get("snippet") or "")[:320],
                "published_at": row.get("date"),
            }
            if len(json.dumps([*results, entry], ensure_ascii=False).encode()) <= WEB_CONTEXT_LIMIT:
                results.append(entry)
        context.update(
            status="completed" if results else "empty",
            results=results,
            message="仅为网页搜索参考，必须核对目标城市/日期；不足以确认时说明不确定，不可当实时观测。",
        )
        usage.status = "completed"
        usage.estimated_cost = Decimal("0.00075") if rows else Decimal("0")
    except (httpx.HTTPError, ProviderFailure, ValueError, KeyError, TypeError) as error:
        context.update(
            status="unavailable", results=[], message="联网查询失败，没有可核实的天气，不可编造。"
        )
        usage.status = "unknown"
        usage.error_code = (
            error.code if isinstance(error, ProviderFailure) else "SEARCH_OUTCOME_UNKNOWN"
        )
    usage.latency_ms = int((time.monotonic() - started) * 1000)
    assistant.search_context = context
    db.commit()
    return context
