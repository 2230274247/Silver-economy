from datetime import UTC

from sqlalchemy import and_, select

from app.models.entities import MemoryFact, MemoryRevision, MemorySource, MemoryUse, Message


def reference_map(db, user_id, assistant_ids):
    if not assistant_ids:
        return {}
    rows = db.execute(
        select(MemoryUse, MemoryFact, MemorySource, Message, MemoryRevision)
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
        .outerjoin(
            MemoryRevision,
            and_(
                MemoryRevision.user_id == MemoryUse.user_id,
                MemoryRevision.memory_id == MemoryUse.memory_id,
                MemoryRevision.revision == MemoryUse.memory_revision,
            ),
        )
        .order_by(MemoryUse.reference_label)
    ).all()
    result = {}
    for use, fact, source, message, revision in rows:
        edited = revision is not None and revision.after.get("value_origin") == "user_edit"
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
                "evidence_text": revision.after["value"] if edited else source.source_excerpt,
                "evidence_origin": "user_edit" if edited else "chat",
                "memory_revision": use.memory_revision,
                "changed_since_reply": use.memory_revision != fact.revision,
            }
        )
    return result
