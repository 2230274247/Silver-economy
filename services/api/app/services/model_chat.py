"""Persist before the paid call. Unknown outcomes never automatically retry."""

import logging
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
from app.models.entities import MemoryFact, MemoryUse, Message, ModelBudget, ModelUsage, User

logger = logging.getLogger("silver.model")
SYSTEM_PROMPT = (PROJECT_ROOT / "prompts/chat-v1.txt").read_text(encoding="utf-8").strip()
MEMORY_PROMPT = (PROJECT_ROOT / "prompts/chat-memory-v3.txt").read_text(encoding="utf-8").strip()


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
    owner = db.scalar(
        select(User)
        .where(User.id == item.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    memory_enabled = owner.memory_enabled
    selected = {}
    prompt = SYSTEM_PROMPT
    if memory_enabled:
        retrieved = MemoryRetriever().retrieve(db, item.user_id, item.content, provider=provider)
        context = ContextBuilder().build(MEMORY_PROMPT, retrieved, item.content)
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
            )
            reserve_budget(db, settings, tokens)
        else:
            tokens = 0
        usage = ModelUsage(
            user_id=item.user_id,
            provider=provider,
            model=settings.deepseek_model if provider == "deepseek" else "mock-v1",
            purpose="chat",
            prompt_version="chat-memory/v3" if memory_enabled else "chat/v1",
            request_id=item.client_request_id,
            reserved_tokens=tokens,
            status="reserved",
        )
        db.add(usage)
        db.commit()  # original + pending reply and quota reservation durable before external I/O
        model = get_provider(settings)
        result = (
            model.complete(prompts, json_output=True) if memory_enabled else model.complete(prompts)
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
        if memory_enabled:
            assistant.raw_model_output = result.content
            try:
                envelope = MemoryAnswerEnvelope.model_validate_json(result.content)
                reply, candidates, rejected = MemoryExtractor().parse(
                    envelope.model_dump_json(exclude={"memory_refs"}), item.content
                )
                candidates = MemoryUpdater().complete_candidates(item.content, candidates)
                assistant.content = reply
                # Consent may have been withdrawn while the paid call was in flight.
                owner = db.scalar(
                    select(User)
                    .where(User.id == item.user_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if owner.memory_enabled:
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
                        extractor_version="chat-memory/v3+state-rule/v1",
                    )
                    item.memory_status = "partial_rejected" if rejected else "captured"
                else:
                    item.memory_status = "disabled"
                    if selected:
                        raise ProviderFailure("MEMORY_CONSENT_CHANGED")
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
