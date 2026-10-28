import copy
import io
from collections import Counter
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT
from app.memory import synthetic_import
from app.memory.retriever import MemoryRetriever
from app.memory.synthetic_data import (
    KINDS,
    SyntheticConfig,
    corpus_summary,
    dataset_lines,
    generate_records,
    users_for,
    validate_lines,
)
from app.models.entities import Conversation, MemoryFact, MemorySource, Message, User


@pytest.mark.parametrize("size", [100, 1000, 10000])
def test_configured_scales_are_unique_diverse_grounded_and_reproducible(size):
    config = SyntheticConfig(memories=size)
    rows = list(generate_records(config))
    summary = corpus_summary(config, rows)
    assert summary["memories"] == summary["unique_values"] == size
    assert set(summary["categories"]) == set(KINDS)
    assert summary["duplicate_observations"] == size // 10
    assert summary["conflict_records"] == size // 10
    assert sum(summary["invalid"].values()) == size // 10
    assert summary["source_messages"] == size + size // 10
    assert set(summary["per_user_memories"]) == {u["id"] for u in users_for(config)}
    assert summary["precision"]["unknown"] > 0
    assert len({r["recorded_at"][:4] for r in rows}) >= 10
    assert any(r["time_expression"] == "上个月" for r in rows)
    assert rows == list(generate_records(config))
    for row in rows:
        assert row["is_synthetic"] and row["key"] in row["value"]
        assert len(row["value"]) <= 1000 and row["event_precision"] in {
            "unknown",
            "year",
            "month",
            "day",
        }
        assert (row["event_at"] is None) == (row["event_precision"] == "unknown")
        assert all(s["text"] == row["value"] for s in row["sources"])


def test_seed_changes_corpus_not_only_identifiers_and_categories_are_configurable():
    a = SyntheticConfig(memories=100, categories=("work", "place"), seed=1)
    b = a.model_copy(update={"seed": 2})
    left, right = list(generate_records(a)), list(generate_records(b))
    assert {r["kind"] for r in left} == {"work", "place"}
    assert [r["value"] for r in left] != [r["value"] for r in right]
    assert len({r["user_id"] for r in left}) == 2


@pytest.mark.parametrize(
    "start,end,reference", [(2000, 2010, "2026-10-26"), (2026, 2026, "2026-01-05")]
)
def test_custom_time_span_bounds_relative_month_events(start, end, reference):
    config = SyntheticConfig(memories=100, start_year=start, end_year=end, reference_date=reference)
    for row in generate_records(config):
        assert start <= datetime.fromisoformat(row["recorded_at"]).year <= end
        if row["event_at"]:
            event = (
                datetime.fromisoformat(row["event_at"])
                .replace(tzinfo=UTC)
                .astimezone(ZoneInfo("Asia/Hong_Kong"))
            )
            assert start <= event.year <= end


@pytest.mark.parametrize(
    "values",
    [
        {"users": 0},
        {"memories": 0},
        {"memories": 100001},
        {"users": 3, "memories": 2},
        {"categories": ()},
        {"categories": ("unknown",)},
        {"categories": ("health", "health")},
        {"conflict_ratio": 0.8, "invalid_ratio": 0.3},
        {"duplicate_ratio": -0.1},
        {"start_year": 2027},
        {"end_year": 2030},
        {"reference_date": "2006-01-01"},
        {"users": 10, "memories": 10, "conflict_ratio": 1, "invalid_ratio": 0},
    ],
)
def test_invalid_configuration_is_rejected(values):
    with pytest.raises(ValueError):
        SyntheticConfig(**values)


def test_golden_small_fixture_is_byte_reproducible_and_reader_rejects_tampering():
    config = SyntheticConfig(
        memories=8, seed=7, duplicate_ratio=0.25, conflict_ratio=0.25, invalid_ratio=0.25
    )
    expected = "".join(dataset_lines(config))
    fixture = PROJECT_ROOT / "tests/memory_eval/fixtures/synthetic-v1-small.jsonl"
    assert fixture.read_bytes() == expected.encode()
    loaded, rows = validate_lines(iter(io.StringIO(expected)))
    assert loaded == config and len(rows) == 8
    lines = expected.splitlines(keepends=True)
    for damaged in [
        lines[:-1],
        [*lines, lines[-1]],
        [lines[0], lines[1].replace("Synthetic", "private"), *lines[2:]],
    ]:
        with pytest.raises(ValueError):
            validate_lines(iter(damaged))


def test_import_is_atomic_idempotent_and_uses_real_owned_sources(db):
    config = SyntheticConfig(memories=100, seed=111)
    rows = list(generate_records(config))
    first = synthetic_import.import_dataset(db, config, rows)
    again = synthetic_import.import_dataset(db, config, rows)
    assert first["inserted_memories"] == 100
    assert again["already_present"] and again["inserted_memories"] == 0
    ids = [u["id"] for u in users_for(config)]
    assert (
        db.scalar(select(func.count()).select_from(MemoryFact).where(MemoryFact.user_id.in_(ids)))
        == 100
    )
    assert (
        db.scalar(select(func.count()).select_from(Message).where(Message.user_id.in_(ids))) == 110
    )
    assert (
        db.scalar(
            select(func.count()).select_from(MemorySource).where(MemorySource.user_id.in_(ids))
        )
        == 110
    )
    for user_id in ids:
        found_count = 0
        for question in ("我现在膝盖怎么样？", "苏州", "工作经历", "习惯", "活动"):
            found = MemoryRetriever().retrieve(db, user_id, question)
            found_count += len(found)
            assert all(
                m.fact.user_id == m.message.user_id == m.source.user_id == user_id for m in found
            )
            assert all(
                m.fact.is_synthetic and m.fact.deleted_at is None and m.fact.retrieval_allowed
                for m in found
            )
        assert found_count > 0
    sources = db.scalars(select(MemorySource).where(MemorySource.user_id.in_(ids))).all()
    assert len({s.message_id for s in sources}) == 110
    assert Counter(s.memory_id for s in sources).most_common(1)[0][1] == 2


@pytest.mark.parametrize("field", ["value", "retrieval_allowed", "source"])
def test_changed_existing_memory_or_evidence_is_never_overwritten(db, field):
    config = SyntheticConfig(memories=10, seed=112)
    rows = list(generate_records(config))
    synthetic_import.import_dataset(db, config, rows)
    fact = db.get(MemoryFact, rows[0]["id"])
    if field == "source":
        changed = db.get(Message, rows[0]["sources"][0]["message_id"])
        changed.content = "Synthetic 用户已纠正的原文"
    elif field == "value":
        fact.value = "Synthetic 用户已纠正的记忆"
    else:
        fact.retrieval_allowed = not fact.retrieval_allowed
    db.flush()
    with pytest.raises(ValueError, match="changed"):
        synthetic_import.import_dataset(db, config, rows)
    if field == "value":
        assert fact.value == "Synthetic 用户已纠正的记忆"


@pytest.mark.parametrize("schema", ["silver_memory_demo_v01", "ALE_AI_MySQL", "mysql"])
def test_import_refuses_non_test_schema_before_any_query(schema):
    bound = SimpleNamespace(
        engine=SimpleNamespace(
            url=make_url(f"mysql+pymysql://silver_demo:synthetic@127.0.0.1:13306/{schema}")
        )
    )
    db = SimpleNamespace(get_bind=lambda: bound)
    with pytest.raises(ValueError, match="isolated"):
        synthetic_import.import_dataset(db, SyntheticConfig(), [])


def test_partial_sql_failure_rolls_back_entire_cohort(db, monkeypatch):
    config = SyntheticConfig(memories=10, seed=113)
    original = synthetic_import.batches

    def fail_last(session, model, rows):
        if model is MemorySource:
            raise RuntimeError("Synthetic injected write failure")
        original(session, model, rows)

    monkeypatch.setattr(synthetic_import, "batches", fail_last)
    with pytest.raises(RuntimeError), db.begin_nested():
        synthetic_import.import_dataset(db, config, list(generate_records(config)))
    ids = [u["id"] for u in users_for(config)]
    for model in (User, Conversation, Message, MemoryFact, MemorySource):
        column = User.id if model is User else model.user_id
        assert db.scalar(select(func.count()).select_from(model).where(column.in_(ids))) == 0


@pytest.mark.parametrize("field", ["user_id", "is_synthetic"])
def test_direct_import_cannot_bypass_manifest_with_foreign_or_non_synthetic_rows(db, field):
    config = SyntheticConfig(memories=10, seed=114)
    rows = copy.deepcopy(list(generate_records(config)))
    if field == "user_id":
        rows[0]["user_id"] = next(
            u["id"] for u in users_for(config) if u["id"] != rows[0]["user_id"]
        )
    else:
        rows[0]["is_synthetic"] = False
    with pytest.raises(ValueError, match="reproducible"):
        synthetic_import.import_dataset(db, config, rows)
