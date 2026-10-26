"""Atomic, non-overwriting imports into the existing isolated TEST schema only."""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import insert, select

from app.core.config import validated_database_url
from app.core.security import hasher
from app.memory.synthetic_data import VERSION, corpus_summary, digest, generate_records, users_for
from app.models.entities import Conversation, MemoryFact, MemorySource, Message, User


def assert_test_session(db):
    # Session may be bound to either an Engine or the integration-test Connection.
    validated_database_url(db.get_bind().engine.url, test_only=True)


def batches(db, model, rows):
    for offset in range(0, len(rows), 500):
        db.execute(insert(model), rows[offset : offset + 500])


def validity_end(record, config):
    if record["conflict_role"] == "before":
        return datetime.fromisoformat(record["recorded_at"]) + timedelta(days=1)
    if record["invalid_type"] == "expired":
        return datetime.combine(config.reference_date, datetime.min.time()) - timedelta(days=1)
    return None


def retrieval_allowed(record):
    return record["invalid_type"] not in {"deleted", "permission_denied"}


def import_dataset(db, config, records):
    """Caller owns the transaction; any failure must roll back the entire import."""
    assert_test_session(db)  # Before the first query or write.
    if len(records) != config.memories or any(
        actual != expected
        for actual, expected in zip(records, generate_records(config), strict=True)
    ):
        raise ValueError("Only the complete reproducible Synthetic corpus can be imported")
    people = users_for(config)
    user_ids = [p["id"] for p in people]
    existing_users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    if any(
        existing_users[p["id"]].login_name != p["login_name"]
        for p in people
        if p["id"] in existing_users
    ):
        raise ValueError("Synthetic user identity collision; nothing overwritten")
    existing = db.scalars(select(MemoryFact).where(MemoryFact.user_id.in_(user_ids))).all()
    summary = corpus_summary(config, records)
    if existing:
        expected = {r["id"]: r for r in records}
        if len(existing) != len(records):
            raise ValueError("Existing cohort differs; refusing to merge or overwrite")
        for fact in existing:
            record = expected.get(fact.id)
            if (
                record is None
                or not fact.is_synthetic
                or fact.extractor_provider != "synthetic"
                or fact.extractor_version != VERSION
                or fact.revision != 1
                or fact.fingerprint != digest(record)
                or fact.value != record["value"]
                or fact.fact_status != record["status"]
                or fact.kind != record["kind"]
                or fact.key != record["key"]
                or fact.retrieval_allowed != retrieval_allowed(record)
                or fact.valid_to != validity_end(record, config)
                or (fact.deleted_at is not None) != (record["invalid_type"] == "deleted")
                or fact.time_expression != record["time_expression"]
                or fact.event_precision != record["event_precision"]
                or fact.recorded_at != datetime.fromisoformat(record["recorded_at"])
                or fact.event_at
                != (datetime.fromisoformat(record["event_at"]) if record["event_at"] else None)
            ):
                raise ValueError("Existing synthetic memory changed; nothing overwritten")
        # Verify original evidence, not just a matching count or fingerprint.
        messages = {
            m.id: m for m in db.scalars(select(Message).where(Message.user_id.in_(user_ids)))
        }
        sources = {
            s.id: s
            for s in db.scalars(select(MemorySource).where(MemorySource.user_id.in_(user_ids)))
        }
        for record in records:
            for source in record["sources"]:
                message, evidence = messages.get(source["message_id"]), sources.get(source["id"])
                if (
                    message is None
                    or evidence is None
                    or message.content != source["text"]
                    or message.user_id != record["user_id"]
                    or message.conversation_id != source["conversation_id"]
                    or message.role != "user"
                    or message.created_at != datetime.fromisoformat(source["created_at"])
                    or evidence.memory_id != record["id"]
                    or evidence.message_id != message.id
                    or evidence.source_excerpt != source["text"]
                    or evidence.user_id != record["user_id"]
                    or evidence.created_at != message.created_at
                ):
                    raise ValueError("Existing synthetic evidence changed; nothing overwritten")
        return {**summary, "already_present": True, "inserted_memories": 0}
    if existing_users:
        raise ValueError("Incomplete existing cohort; nothing overwritten")
    batches(
        db,
        User,
        [
            {**p, "password_hash": hasher.hash(secrets.token_urlsafe(32)), "memory_enabled": True}
            for p in people
        ],
    )
    conversations, messages, facts, sources = {}, [], [], []
    expired = datetime.combine(config.reference_date, datetime.min.time()) - timedelta(days=1)
    for record in records:
        recorded = datetime.fromisoformat(record["recorded_at"])
        for source in record["sources"]:
            at = datetime.fromisoformat(source["created_at"])
            conversations.setdefault(
                source["conversation_id"],
                {
                    "id": source["conversation_id"],
                    "user_id": record["user_id"],
                    "title": f"Synthetic {at:%Y-%m}",
                    "created_at": at,
                    "last_message_at": at,
                },
            )
            conversation = conversations[source["conversation_id"]]
            conversation["created_at"] = min(conversation["created_at"], at)
            conversation["last_message_at"] = max(conversation["last_message_at"], at)
            messages.append(
                {
                    "id": source["message_id"],
                    "user_id": record["user_id"],
                    "conversation_id": source["conversation_id"],
                    "role": "user",
                    "content": source["text"],
                    "created_at": at,
                    "updated_at": at,
                    "status": "saved",
                    "memory_status": "synthetic_import",
                }
            )
            sources.append(
                {
                    "id": source["id"],
                    "user_id": record["user_id"],
                    "memory_id": record["id"],
                    "message_id": source["message_id"],
                    "source_excerpt": source["text"],
                    "created_at": at,
                }
            )
        facts.append(
            {
                "id": record["id"],
                "user_id": record["user_id"],
                "kind": record["kind"],
                "key": record["key"],
                "value": record["value"],
                "fact_status": record["status"],
                "created_at": recorded,
                "updated_at": recorded,
                "recorded_at": recorded,
                "event_at": datetime.fromisoformat(record["event_at"])
                if record["event_at"]
                else None,
                "time_expression": record["time_expression"],
                "event_precision": record["event_precision"],
                "event_timezone": "Asia/Hong_Kong",
                "confirmed_at": recorded,
                "deleted_at": expired if record["invalid_type"] == "deleted" else None,
                "valid_to": validity_end(record, config),
                "retrieval_allowed": retrieval_allowed(record),
                "confidence_label": "synthetic_fixture",
                "fingerprint": digest(record),
                "extractor_provider": "synthetic",
                "extractor_version": VERSION,
                "is_synthetic": True,
                "revision": 1,
                "value_origin": "chat",
            }
        )
    batches(db, Conversation, list(conversations.values()))
    batches(db, Message, messages)
    batches(db, MemoryFact, facts)
    batches(db, MemorySource, sources)
    db.flush()
    return {**summary, "already_present": False, "inserted_memories": len(facts)}
