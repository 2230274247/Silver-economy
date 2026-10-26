"""Persist before the paid call. Unknown outcomes never automatically retry."""

import logging
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from app.core.config import PROJECT_ROOT, get_settings
from app.llm.providers import ProviderFailure, get_provider
from app.models.entities import Message, ModelBudget, ModelUsage

logger = logging.getLogger("silver.model")
SYSTEM_PROMPT = (PROJECT_ROOT / "prompts/chat-v1.txt").read_text(encoding="utf-8").strip()


def context_messages(db, item):
    # Bound both message count and UTF-8 bytes; never send every historical message.
    history = db.scalars(
        select(Message)
        .where(
            Message.user_id == item.user_id,
            Message.conversation_id == item.conversation_id,
            Message.created_at <= item.created_at,
            Message.status.in_(["saved", "completed"]),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(12)
    ).all()
    selected, size = [], len(SYSTEM_PROMPT.encode("utf-8"))
    for message in history:
        if message.provider == "mock":
            continue
        cost = len(message.content.encode("utf-8")) + 32
        if size + cost > 8000:
            break
        selected.append({"role": message.role, "content": message.content})
        size += cost
    return [{"role": "system", "content": SYSTEM_PROMPT}, *reversed(selected)]


def reserve_budget(db, settings, tokens):
    day = datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
    db.execute(
        insert(ModelBudget)
        .values(day=day, requests=0, reserved_tokens=0)
        .on_duplicate_key_update(day=day)
    )
    budget = db.scalar(select(ModelBudget).where(ModelBudget.day == day).with_for_update())
    if (
        budget.requests >= settings.deepseek_daily_request_limit
        or budget.reserved_tokens + tokens > settings.deepseek_daily_token_limit
    ):
        raise ProviderFailure("MODEL_BUDGET_EXCEEDED")
    budget.requests += 1
    budget.reserved_tokens += tokens


def generate_reply(db, item, assistant):
    settings = get_settings()
    provider = settings.llm_provider
    assistant.provider = provider
    prompts = context_messages(db, item)
    usage = None
    started = time.monotonic()
    try:
        if provider == "deepseek":
            if not settings.deepseek_api_key.get_secret_value().strip():
                raise ProviderFailure("MODEL_NOT_CONFIGURED")
            # UTF-8 bytes plus framing is a conservative token upper estimate for
            # this bounded text-only prompt, and includes max output reservation.
            tokens = (
                sum(len(m["content"].encode("utf-8")) + 64 for m in prompts)
                + settings.deepseek_max_output_tokens
                + 256
            )
            reserve_budget(db, settings, tokens)
        else:
            tokens = 0
        usage = ModelUsage(
            user_id=item.user_id,
            provider=provider,
            model=settings.deepseek_model if provider == "deepseek" else "mock-v1",
            purpose="chat",
            request_id=item.client_request_id,
            reserved_tokens=tokens,
            status="reserved",
        )
        db.add(usage)
        db.commit()  # original + pending reply and quota reservation durable before external I/O
        result = get_provider(settings).complete(prompts)
        assistant.content = result.content
        assistant.status = "completed"
        assistant.error_code = None
        usage.model = result.model
        usage.input_tokens, usage.output_tokens = result.input_tokens, result.output_tokens
        usage.status = "completed"
        # Worst-case peak cache-miss estimate for the documented default model,
        # not a vendor bill; unknown custom models have no fabricated price.
        usage.estimated_cost = (
            (
                Decimal(result.input_tokens) * Decimal("0.3")
                + Decimal(result.output_tokens) * Decimal("1.2")
            )
            / 1000000
            if provider == "deepseek" and result.model.startswith("deepseek-flash")
            else None
        )
    except ProviderFailure as error:
        assistant.status = "failed"
        assistant.error_code = error.code
        if usage:
            usage.status, usage.error_code = "unknown", error.code
        # Keep quota reserved even when outcome is unknown; no blind retries.
    finally:
        if usage:
            usage.latency_ms = int((time.monotonic() - started) * 1000)
        db.commit()
    logger.info(
        "request_id=%s provider=%s status=%s latency_ms=%s "
        "input_tokens=%s output_tokens=%s estimated_usd=%s",
        item.client_request_id,
        provider,
        assistant.status,
        int((time.monotonic() - started) * 1000),
        usage.input_tokens if usage else None,
        usage.output_tokens if usage else None,
        usage.estimated_cost if usage else None,
    )
