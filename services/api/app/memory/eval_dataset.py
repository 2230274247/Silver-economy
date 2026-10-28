"""Test-only benchmark materialization. The sealed suite is independent of ranking."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.core.security import hasher, utc_now
from app.memory.extractor import event_time
from app.memory.synthetic_data import SyntheticConfig, digest, generate_records, users_for
from app.memory.synthetic_import import assert_test_session, import_dataset
from app.memory.updater import MemoryUpdater
from app.models.entities import Conversation, MemoryFact, MemorySource, Message, User
from app.schemas.memory import (
    MemoryConfirmation,
    MemoryCorrection,
    MemoryMutation,
    MemoryPermission,
)

SUITE_PATH = PROJECT_ROOT / "tests/memory_eval/fixtures/suite-v1.json"
CACHE = PROJECT_ROOT / ".cache/memory-eval"


def load_suite():
    raw = SUITE_PATH.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SUITE_PATH.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen evaluation suite seal mismatch")
    suite = json.loads(raw)
    if suite["version"] != "memory-eval/1" or not suite["synthetic"]:
        raise ValueError("Unsupported evaluation suite")
    return suite, sha


def identity(namespace, label):
    return str(uuid.uuid5(uuid.UUID(namespace), label))


def data_snapshot(db, user_ids):
    """Canonical factual state, excluding random credentials/audit clocks and chat traffic."""
    assert_test_session(db)
    now = utc_now()
    result = hashlib.sha256()
    count = 0
    statement = select(MemoryFact).where(MemoryFact.user_id.in_(user_ids)).order_by(MemoryFact.id)
    for fact in db.scalars(statement.execution_options(yield_per=500)):
        data = [
            fact.id,
            fact.user_id,
            fact.kind,
            fact.key,
            fact.value,
            fact.fact_status,
            str(fact.event_at),
            fact.event_precision,
            fact.time_expression,
            fact.deleted_at is not None,
            fact.retrieval_allowed,
            fact.revision,
            fact.value_origin,
            fact.is_synthetic,
            fact.extractor_provider,
            fact.valid_to is not None and fact.valid_to <= now,
            fact.valid_from is not None and fact.valid_from > now,
        ]
        result.update(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode())
        count += 1
    sources = (
        select(MemorySource).where(MemorySource.user_id.in_(user_ids)).order_by(MemorySource.id)
    )
    for source in db.scalars(sources.execution_options(yield_per=500)):
        result.update(
            json.dumps(
                [
                    source.id,
                    source.user_id,
                    source.memory_id,
                    source.message_id,
                    source.source_excerpt,
                ],
                ensure_ascii=False,
            ).encode()
        )
    return {"sha256": result.hexdigest(), "memories": count}


def prepare_dataset(engine, scale, suite, suite_sha):
    if scale < len(suite["facts"]):
        raise ValueError("Scale cannot omit fixed facts")
    namespace = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{suite_sha}:{scale}"))
    directory = CACHE / f"benchmark-{namespace}"
    state_path, credentials_path = directory / "state.json", directory / "credentials.json"
    noise_count = scale - len(suite["facts"])
    config = (
        SyntheticConfig(memories=noise_count, seed=int(suite_sha[:12], 16)) if noise_count else None
    )
    people = (
        users_for(config)
        if config
        else [
            {"id": identity(namespace, actor), "login_name": f"syn-bench-{namespace[:12]}-{actor}"}
            for actor in ("A", "B")
        ]
    )
    user_ids = [p["id"] for p in people]
    mapping = {f["id"]: identity(namespace, "memory:" + f["id"]) for f in suite["facts"]}
    sources = {f["id"]: identity(namespace, "message:" + f["id"]) for f in suite["facts"]}
    with Session(engine) as db:
        assert_test_session(db)
        present = db.scalar(select(func.count()).select_from(User).where(User.id.in_(user_ids)))
        if present:
            if not state_path.exists() or not credentials_path.exists():
                raise ValueError("Existing benchmark is incomplete; never overwrite it")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if (
                state["suite_sha256"] != suite_sha
                or data_snapshot(db, user_ids) != state["snapshot"]
            ):
                raise ValueError(
                    "Benchmark facts changed; rebuild only through isolated schema tests"
                )
            return state, json.loads(credentials_path.read_text(encoding="utf-8"))
    credentials = {
        actor: {"login_name": p["login_name"], "password": secrets.token_urlsafe(24)}
        for actor, p in zip(("A", "B"), people, strict=True)
    }
    with Session(engine) as db, db.begin():
        assert_test_session(db)
        if config:
            import_dataset(db, config, list(generate_records(config)))
        else:
            db.add_all(
                [
                    User(
                        **p,
                        password_hash=hasher.hash(credentials[a]["password"]),
                        memory_enabled=True,
                    )
                    for a, p in zip(("A", "B"), people, strict=True)
                ]
            )
            db.flush()
        for actor, p in zip(("A", "B"), people, strict=True):
            owner = db.scalar(select(User).where(User.id == p["id"]).with_for_update())
            if owner.login_name != p["login_name"]:
                raise ValueError("Benchmark user identity mismatch")
            owner.password_hash = hasher.hash(credentials[actor]["password"])
        updater = MemoryUpdater()
        for definition in suite["facts"]:
            actor = definition["actor"]
            owner = people[0 if actor == "A" else 1]["id"]
            at = datetime.fromisoformat(definition["recorded_at"])
            conversation_id = identity(namespace, "conversation:" + definition["id"])
            db.add(
                Conversation(
                    id=conversation_id, user_id=owner, title="Synthetic 固定评估来源", created_at=at
                )
            )
            db.flush()
            message = Message(
                id=sources[definition["id"]],
                user_id=owner,
                conversation_id=conversation_id,
                role="user",
                content=definition["text"],
                created_at=at,
                updated_at=at,
                memory_status="synthetic_fixture",
            )
            db.add(message)
            when, precision = event_time(definition["time_expression"], at)
            fact = MemoryFact(
                id=mapping[definition["id"]],
                user_id=owner,
                kind=definition["kind"],
                key=definition["key"],
                value=definition["text"],
                recorded_at=at,
                created_at=at,
                event_at=when,
                event_precision=precision,
                time_expression=definition["time_expression"] or None,
                fact_status="candidate",
                retrieval_allowed=True,
                is_synthetic=True,
                extractor_provider="synthetic",
                extractor_version=suite["version"],
                confidence_label="synthetic_fixture",
                fingerprint=digest(definition),
            )
            db.add(fact)
            db.flush()
            action = definition["action"]
            if action != "untraceable":
                db.add(
                    MemorySource(
                        id=identity(namespace, "source:" + definition["id"]),
                        user_id=owner,
                        memory_id=fact.id,
                        message_id=message.id,
                        source_excerpt=definition["text"],
                        created_at=at,
                    )
                )
                db.flush()
            if action == "edit":
                payload = MemoryCorrection(
                    expected_revision=1,
                    kind=fact.kind,
                    key=fact.key,
                    value=definition["corrected_text"],
                    time_expression=fact.time_expression or "",
                )
                updater.apply(db, fact, "correct", payload)
            elif action == "delete":
                updater.apply(db, fact, "delete", MemoryMutation(expected_revision=1))
            elif action == "inactive":
                updater.apply(db, fact, "invalidate", MemoryMutation(expected_revision=1))
            elif action == "permission":
                updater.apply(
                    db, fact, "permission", MemoryPermission(expected_revision=1, allowed=False)
                )
            else:
                updater.apply(
                    db, fact, "confirm", MemoryConfirmation(expected_revision=1, confirmed=True)
                )
                if action == "historical":
                    fact.fact_status = "historical"
                    fact.valid_to = datetime(2025, 1, 1)
                elif action == "expired":
                    fact.valid_to = datetime(2020, 1, 1)
                elif action == "future":
                    fact.valid_from = datetime(2099, 1, 1)
                elif action in {"health_before", "health_after"}:
                    updater.reconcile(db, message, [fact])
            db.flush()
        snapshot = data_snapshot(db, user_ids)
        if snapshot["memories"] != scale:
            raise ValueError("Benchmark scale mismatch")
    state = {
        "namespace": namespace,
        "suite_sha256": suite_sha,
        "scale": scale,
        "noise_memories": noise_count,
        "actors": dict(zip(("A", "B"), user_ids, strict=True)),
        "mapping": mapping,
        "source_messages": sources,
        "snapshot": snapshot,
        "noise_config": config.model_dump(mode="json") if config else None,
    }
    directory.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state, credentials
