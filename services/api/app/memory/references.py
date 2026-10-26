from datetime import UTC

from sqlalchemy import and_, select

from app.models.entities import MemoryFact, MemorySource, MemoryUse, Message


def reference_map(db, user_id, assistant_ids):
    if not assistant_ids:
        return {}
    rows = db.execute(
        select(MemoryUse, MemoryFact, MemorySource, Message)
        .join(
            MemoryFact,
            and_(MemoryFact.id == MemoryUse.memory_id, MemoryFact.user_id == MemoryUse.user_id),
        )
        .join(
            MemorySource,
            and_(
                MemorySource.memory_id == MemoryUse.memory_id,
                MemorySource.user_id == MemoryUse.user_id,
                MemorySource.message_id == MemoryUse.source_message_id,
            ),
        )
        .join(
            Message,
            and_(Message.id == MemorySource.message_id, Message.user_id == MemorySource.user_id),
        )
        .where(
            MemoryUse.user_id == user_id,
            MemoryUse.assistant_message_id.in_(assistant_ids),
            MemoryFact.deleted_at.is_(None),
        )
        .order_by(MemoryUse.reference_label)
    ).all()
    result = {}
    for use, fact, source, message in rows:
        result.setdefault(use.assistant_message_id, []).append(
            {
                "label": use.reference_label,
                "memory_id": fact.id,
                "source_message_id": message.id,
                "conversation_id": message.conversation_id,
                "source_excerpt": source.source_excerpt,
                "recorded_at": message.created_at.replace(tzinfo=UTC).isoformat(),
                "status": fact.fact_status,
                "confirmed": fact.confirmed_at is not None,
                "is_synthetic": fact.is_synthetic,
                "extractor_provider": fact.extractor_provider,
            }
        )
    return result
