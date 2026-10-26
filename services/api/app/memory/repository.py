from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.memory.extractor import event_time
from app.memory.updater import MemoryUpdater, fingerprint
from app.models.entities import MemoryFact, MemorySource


class MemoryRepository:
    def save_candidates(
        self, db, message, candidates, provider, *, extractor_version="chat-memory/v1"
    ):
        saved = []
        for candidate in candidates:
            when, precision = event_time(candidate.time_expression, message.created_at)
            digest = fingerprint(provider, candidate.kind, candidate.key, candidate.value, when)
            statement = select(MemoryFact).where(
                MemoryFact.user_id == message.user_id, MemoryFact.fingerprint == digest
            )
            fact = db.scalar(statement)
            if not fact:
                try:
                    with db.begin_nested():
                        fact = MemoryFact(
                            user_id=message.user_id,
                            kind=candidate.kind,
                            key=candidate.key,
                            value=candidate.value,
                            fingerprint=digest,
                            time_expression=candidate.time_expression or None,
                            event_at=when,
                            event_precision=precision,
                            state_text=candidate.state_text or None,
                            fact_status="candidate",
                            retrieval_allowed=True,
                            extractor_provider=provider,
                            extractor_version=extractor_version,
                            confidence_label="explicit_span",
                        )
                        db.add(fact)
                        db.flush()
                except IntegrityError:
                    fact = db.scalar(statement)
            if fact is None or fact.deleted_at:
                continue
            source = db.scalar(
                select(MemorySource).where(
                    MemorySource.user_id == message.user_id,
                    MemorySource.memory_id == fact.id,
                    MemorySource.message_id == message.id,
                )
            )
            if not source:
                db.add(
                    MemorySource(
                        user_id=message.user_id,
                        memory_id=fact.id,
                        message_id=message.id,
                        source_excerpt=candidate.source_excerpt,
                    )
                )
            saved.append(fact)
        db.flush()
        MemoryUpdater().reconcile(db, message, saved)
        return saved
