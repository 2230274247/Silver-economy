"""User-controlled revisions and narrow, evidence-based state transitions.

Callers lock the owning User before any fact, matching chat/consent lock order.
No model calls, raw-message edits, hard deletes or background re-extraction.
"""

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errors import ApiError
from app.memory.extractor import MemoryCandidate, event_time
from app.models.entities import MemoryFact, MemoryRevision, User


def fingerprint(provider, kind, key, value, when):
    return hashlib.sha256(f"{provider}|{kind}|{key}|{value}|{when}".encode()).hexdigest()


def snapshot(fact):
    return {
        "key": fact.key,
        "value": fact.value,
        "kind": fact.kind,
        "status": fact.fact_status,
        "time_expression": fact.time_expression,
        "event_at": fact.event_at.isoformat() if fact.event_at else None,
        "event_precision": fact.event_precision,
        "retrieval_allowed": fact.retrieval_allowed,
        "confirmed": fact.confirmed_at is not None,
        "value_origin": fact.value_origin,
    }


def audit(db, fact, before, action, actor="user"):
    fact.revision += 1
    db.add(
        MemoryRevision(
            user_id=fact.user_id,
            memory_id=fact.id,
            revision=fact.revision,
            before=before,
            after=snapshot(fact),
            action=action,
            actor=actor,
        )
    )


class MemoryUpdater:
    def complete_candidates(self, source, candidates):
        # A narrow explicit statement must not be lost just because a model
        # returns an empty candidate list. No inference or paid retry is used.
        match = re.fullmatch(
            r"(?:我的?|本人)([左右]?(?:膝盖|膝|肩膀|脚踝|手腕|腰|腿|脚|手))"
            r"(?:已经|现在|目前|完全|现在已经|已经完全)?"
            r"(好了|恢复了|完全恢复了|痊愈了|受伤了|疼痛|摔伤了)[。！]?",
            source.strip(),
        )
        if match and not any(c.kind == "health" and c.value == source.strip() for c in candidates):
            return [
                *candidates,
                MemoryCandidate(
                    kind="health",
                    key=match[1],
                    value=source.strip(),
                    source_excerpt=source.strip(),
                    state_text=match[2],
                ),
            ]
        return candidates

    def owned_for_update(self, db, user_id, memory_id, revision):
        db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        fact = db.scalar(
            select(MemoryFact)
            .where(
                MemoryFact.id == memory_id,
                MemoryFact.user_id == user_id,
                MemoryFact.deleted_at.is_(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if fact is None:
            raise ApiError(404, "NOT_FOUND", "记忆不存在或无法访问")
        if fact.revision != revision:
            raise ApiError(409, "MEMORY_REVISION_CONFLICT", "记忆已发生变化，请重新读取后再修改")
        return fact

    def apply(self, db, fact, action, payload):
        before = snapshot(fact)
        now = datetime.now(UTC).replace(tzinfo=None)
        if action == "confirm":
            fact.confirmed_at = now if payload.confirmed else None
            if fact.fact_status in {"candidate", "confirmed", "active"}:
                fact.fact_status = "confirmed" if payload.confirmed else "candidate"
        elif action == "correct":
            kind, key, value = payload.kind, payload.key.strip(), payload.value.strip()
            expression = payload.time_expression.strip() or None
            when, precision = fact.event_at, fact.event_precision
            if expression != fact.time_expression:
                when, precision = event_time(expression or "", now)
            new_hash = fingerprint(fact.extractor_provider, kind, key, value, when)
            duplicate = db.scalar(
                select(MemoryFact.id).where(
                    MemoryFact.user_id == fact.user_id,
                    MemoryFact.fingerprint == new_hash,
                    MemoryFact.id != fact.id,
                )
            )
            if duplicate:
                raise ApiError(409, "MEMORY_DUPLICATE", "已有相同记忆，未覆盖原记录")
            fact.kind, fact.key, fact.value = kind, key, value
            fact.event_at, fact.event_precision, fact.time_expression = when, precision, expression
            fact.fingerprint, fact.value_origin = new_hash, "user_edit"
            fact.confirmed_at, fact.fact_status = now, "confirmed"
            fact.valid_to, fact.valid_from, fact.state_text = None, None, None
        elif action == "invalidate":
            fact.fact_status, fact.valid_to = "inactive", now
        elif action == "permission":
            fact.retrieval_allowed = payload.allowed
        elif action == "delete":
            fact.deleted_at, fact.retrieval_allowed, fact.fact_status = now, False, "deleted"
        audit(db, fact, before, action)

    def reconcile(self, db, message, saved):
        """Only explicit first-person body/state transitions; ambiguous claims stay candidates.

        Never use the model's state_text alone: '恢复' can occur in '没有恢复'.
        Historical facts remain traceable, but do not describe the current state.
        """
        for fact in saved[-1:]:
            state = health_state(fact.value) if fact.kind == "health" else None
            if state is None or fact.fact_status not in {"candidate", "confirmed", "active"}:
                continue
            is_past = any(word in fact.value for word in ("以前", "当时", "去年", "上个月", "曾经"))
            body, _ = state
            previous = db.scalars(
                select(MemoryFact)
                .where(
                    MemoryFact.user_id == message.user_id,
                    MemoryFact.id != fact.id,
                    MemoryFact.kind == "health",
                    MemoryFact.deleted_at.is_(None),
                    MemoryFact.fact_status.in_(["active", "candidate", "confirmed"]),
                    MemoryFact.extractor_provider == fact.extractor_provider,
                )
                .with_for_update()
            ).all()
            for older in previous:
                old_state = health_state(older.value)
                if old_state and old_state[0] == body and old_state[1] != state[1]:
                    if is_past:
                        before = snapshot(fact)
                        fact.fact_status, fact.valid_to = "historical", message.created_at
                        audit(db, fact, before, "historical_retelling", "evidence_rule")
                        break
                    before = snapshot(older)
                    older.fact_status = "historical"
                    older.valid_to = message.created_at
                    audit(db, older, before, "state_superseded", "evidence_rule")


def health_state(text):
    if any(
        word in text
        for word in (
            "没有",
            "没好",
            "未",
            "不",
            "好像",
            "可能",
            "也许",
            "如果",
            "假如",
            "朋友",
            "阿姨",
            "他",
            "她",
            "？",
            "?",
        )
    ):
        return None
    match = re.search(
        r"(?:我的?|本人)(?P<body>[左右]?(?:膝盖|膝|肩膀|脚踝|手腕|腰|腿|脚|手))", text
    )
    if not match:
        return None
    tail = text[match.end() :]
    if any(word in tail for word in ("恢复", "好了", "痊愈")):
        return match["body"].replace("膝盖", "膝"), "recovered"
    if any(word in tail for word in ("受伤", "疼痛", "摔伤")):
        return match["body"].replace("膝盖", "膝"), "injured"
    return None
