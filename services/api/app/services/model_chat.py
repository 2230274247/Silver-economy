"""Persist before the paid call. Unknown outcomes never automatically retry."""

import json
import logging
import re
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from app.core.config import PROJECT_ROOT, get_settings
from app.llm.providers import ProviderFailure, get_provider
from app.memory.context import MAX_CONTEXT_BYTES, ContextBuilder, MemoryAnswerEnvelope
from app.memory.extractor import MemoryExtractor
from app.memory.repository import MemoryRepository
from app.memory.retriever import (
    MemoryRetriever,
    evidence_signature,
    historical_query,
    valid_context_fact,
)
from app.memory.updater import MemoryUpdater
from app.models.entities import (
    AdminModelBudget,
    MemoryFact,
    MemoryUse,
    Message,
    ModelBudget,
    ModelUsage,
    User,
)
from app.schemas.tasks import TaskEnvelope
from app.services.weather_search import WEB_CONTEXT_LIMIT, WEB_MARKER, search_weather, weather_plan
from app.tasks.intent import task_context
from app.tasks.repository import save_candidates as save_task_candidates

logger = logging.getLogger("silver.model")
SYSTEM_PROMPT = (PROJECT_ROOT / "prompts/chat-v2.txt").read_text(encoding="utf-8").strip()
MEMORY_PROMPT = (PROJECT_ROOT / "prompts/chat-memory-v4.txt").read_text(encoding="utf-8").strip()


def context_messages(db, item, system_prompt=SYSTEM_PROMPT):
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
    selected, size = [], len(system_prompt.encode("utf-8")) + 32
    for message in history:
        if message.provider == "mock":
            continue
        cost = len(message.content.encode("utf-8")) + 32
        if size + cost > MAX_CONTEXT_BYTES:
            break
        selected.append({"role": message.role, "content": message.content})
        size += cost
    return [{"role": "system", "content": system_prompt}, *reversed(selected)]


def reserve_budget(db, settings, tokens, *, budget_model=ModelBudget):
    day = datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()
    db.execute(
        insert(budget_model)
        .values(day=day, requests=0, reserved_tokens=0)
        .on_duplicate_key_update(day=day)
    )
    budget = db.scalar(select(budget_model).where(budget_model.day == day).with_for_update())
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
    owner = db.scalar(
        select(User)
        .where(User.id == item.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    memory_enabled = owner.memory_enabled
    budget_model = AdminModelBudget if owner.is_admin else ModelBudget
    if owner.is_admin:
        settings = settings.model_copy(
            update={
                "deepseek_daily_request_limit": settings.admin_daily_request_limit,
                "deepseek_daily_token_limit": settings.admin_daily_token_limit,
                "deepseek_max_output_tokens": settings.admin_max_output_tokens,
            }
        )
    public = "\nPUBLIC_MODEL_CONTEXT_JSON=" + json.dumps(
        {
            "provider": provider,
            "model": settings.deepseek_model if provider == "deepseek" else "mock-v1",
            "now": datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(),
            "timezone": "Asia/Hong_Kong",
        },
        ensure_ascii=False,
    )
    weather = weather_plan(item.content)
    city_answer = item.content.strip().rstrip("。！!，, ")
    if (
        weather is None
        and re.fullmatch(r"[\u4e00-\u9fff]{2,8}", city_answer)
        and city_answer not in {"好的", "谢谢", "你好", "不知道", "随便", "算了"}
    ):
        previous = db.scalar(
            select(Message)
            .where(
                Message.user_id == item.user_id,
                Message.conversation_id == item.conversation_id,
                Message.role == "assistant",
                Message.created_at < item.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        if previous and (previous.search_context or {}).get("status") == "missing_location":
            weather = weather_plan(city_answer + "天气")
            weather["date"] = previous.search_context["date"]
            weather["query"] = f"{city_answer} {weather['date']} 天气预报 中国天气网 气象台"
    public += "\nWEATHER_SEARCH_CONTEXT_JSON=" + (
        WEB_MARKER if weather else '{"status":"not_requested"}'
    )
    selected = {}
    prompt = SYSTEM_PROMPT + public
    task = task_context(
        db,
        item,
        MEMORY_PROMPT
        + public
        + (
            "\n当前长期记忆已授权。"
            if memory_enabled
            else "\n当前未授权长期记忆，memories和memory_refs必须为空。"
        ),
    )
    if task:
        prompt = task.prompt
        settings = settings.model_copy(
            update={
                "deepseek_max_output_tokens": max(
                    settings.deepseek_max_output_tokens, settings.deepseek_task_max_output_tokens
                )
                if owner.is_admin
                else settings.deepseek_task_max_output_tokens
            }
        )
    if memory_enabled or task:
        # Drafts are grounded in the explicit request/pending draft, never an inferred home address.
        retrieved = (
            MemoryRetriever().retrieve(db, item.user_id, item.content, provider=provider)
            if memory_enabled
            else []
        )
        context = ContextBuilder().build(
            prompt if task else MEMORY_PROMPT + public, retrieved, item.content
        )
        prompt, selected = context.system_prompt, context.selected
    prompts = context_messages(db, item, prompt)
    item.memory_status = "pending" if memory_enabled else "disabled"
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
                + (WEB_CONTEXT_LIMIT + 1000 if weather else 0)
            )
            reserve_budget(db, settings, tokens, budget_model=budget_model)
        else:
            tokens = 0
        usage = ModelUsage(
            user_id=item.user_id,
            provider=provider,
            model=settings.deepseek_model if provider == "deepseek" else "mock-v1",
            purpose="chat_task" if task else "chat",
            prompt_version="chat-task/v2"
            if task
            else "chat-memory/v4"
            if memory_enabled
            else "chat/v2",
            request_id=item.client_request_id,
            reserved_tokens=tokens,
            status="reserved",
        )
        db.add(usage)
        db.commit()  # original + pending reply and quota reservation durable before external I/O
        if weather:
            live = search_weather(
                db,
                item,
                assistant,
                settings,
                weather,
                lambda db, settings, tokens: reserve_budget(
                    db, settings, tokens, budget_model=budget_model
                ),
            )
            assistant.search_context = live
            prompt = prompt.replace(WEB_MARKER, json.dumps(live, ensure_ascii=False))
            prompts = context_messages(db, item, prompt)
        model = get_provider(settings)
        result = (
            model.complete(prompts, json_output=True)
            if memory_enabled or task
            else model.complete(prompts)
        )
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
        if memory_enabled or task:
            assistant.raw_model_output = result.content
            try:
                envelope = (TaskEnvelope if task else MemoryAnswerEnvelope).model_validate_json(
                    result.content
                )
                reply, candidates, rejected = (
                    MemoryExtractor().parse(
                        envelope.model_dump_json(exclude={"memory_refs", "outings"}), item.content
                    )
                    if memory_enabled
                    else (envelope.reply, [], 0)
                )
                if memory_enabled:
                    candidates = MemoryUpdater().complete_candidates(item.content, candidates)
                if task:
                    factual = [
                        candidate
                        for candidate in candidates
                        if not (
                            re.search(r"明天|后天|下周|打算|准备", candidate.source_excerpt)
                            or candidate.kind in {"event", "travel", "date"}
                            and any(
                                candidate.source_excerpt in outing.source_excerpt
                                or outing.source_excerpt in candidate.source_excerpt
                                for outing in envelope.outings
                            )
                        )
                    ]
                    rejected += len(candidates) - len(factual)
                    candidates = factual
                assistant.content = reply
                # Consent may have been withdrawn while the paid call was in flight.
                owner = db.scalar(
                    select(User)
                    .where(User.id == item.user_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if memory_enabled and owner.memory_enabled:
                    labels = list(dict.fromkeys(envelope.memory_refs))
                    if any(label not in selected for label in labels):
                        raise ProviderFailure("MEMORY_UNSUPPORTED_REFERENCE")
                    # Editing/deleting/revoking while generation is in flight must
                    # not return an answer grounded in stale private evidence.
                    for label in labels:
                        memory = selected[label]
                        fact = db.scalar(
                            select(MemoryFact)
                            .where(
                                MemoryFact.id == memory.fact.id, MemoryFact.user_id == item.user_id
                            )
                            .with_for_update()
                            .execution_options(populate_existing=True)
                        )
                        if (
                            fact is None
                            or not valid_context_fact(
                                fact, include_historical=historical_query(item.content)
                            )
                            or evidence_signature(fact) != memory.evidence_snapshot
                        ):
                            raise ProviderFailure("MEMORY_CHANGED_DURING_REPLY")
                    for label in labels:
                        memory = selected[label]
                        db.add(
                            MemoryUse(
                                user_id=item.user_id,
                                assistant_message_id=assistant.id,
                                memory_id=memory.fact.id,
                                source_message_id=memory.source.message_id,
                                reference_label=label,
                                memory_revision=memory.fact.revision,
                            )
                        )
                    MemoryRepository().save_candidates(
                        db,
                        item,
                        candidates,
                        provider,
                        extractor_version=(
                            "chat-task/v2+state-rule/v1" if task else "chat-memory/v4+state-rule/v1"
                        ),
                    )
                    item.memory_status = "partial_rejected" if rejected else "captured"
                else:
                    item.memory_status = "disabled"
                    if selected:
                        raise ProviderFailure("MEMORY_CONSENT_CHANGED")
                if task:
                    # A nested transaction prevents a multi-draft operation being half applied.
                    with db.begin_nested():
                        drafts = save_task_candidates(db, item, envelope.outings, task, provider)
                    # Keep the model's conversational reply; execution state belongs to the card.
                    assistant.content = re.sub(
                        r"已(?:经)?(?:为你|帮你|替你|为您|帮您)?(?:安排|设置|保存).{0,8}提醒"
                        r"|(?:我会|会为你|会帮你|会准时|会按时).{0,8}提醒",
                        "这项提醒尚待你确认",
                        assistant.content,
                    )
                    if drafts:
                        assistant.content += "\n提醒尚未安排，请在下方卡片核对并确认。"
            except (ValidationError, ValueError):
                item.memory_status = "failed_schema"
                assistant.content, assistant.status = "", "failed"
                assistant.error_code = "MODEL_RESPONSE_FORMAT"
    except ProviderFailure as error:
        assistant.status = "failed"
        assistant.error_code = error.code
        assistant.content = ""
        if memory_enabled:
            item.memory_status = "model_failed"
        if usage:
            usage.status = "completed_rejected" if usage.status == "completed" else "unknown"
            usage.error_code = error.code
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
