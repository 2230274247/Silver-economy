from datetime import datetime

from sqlalchemy import select

from app.models.entities import MemoryFact, MemorySource, ModelUsage
from tests.test_memory_retrieval import remember


def test_calendar_precision_source_count_and_recording_time_are_distinct(db, accounts, clients):
    year, source, _ = remember(
        db,
        accounts[0][0],
        kind="travel",
        key="苏州",
        value="2019年我去过苏州旅游",
        expression="2019年",
    )
    month, _, _ = remember(db, accounts[0][0], value="上个月我膝盖受伤了")
    unknown, _, _ = remember(
        db, accounts[0][0], kind="interest", key="书法", value="我喜欢书法", expression=""
    )
    rows = clients[0].get("/api/v1/memories/timeline").json()["items"]
    indexed = {row["id"]: row for row in rows}
    assert indexed[year.id]["event_label"] == "2019年"
    assert indexed[month.id]["event_label"].endswith("月")
    assert indexed[unknown.id]["event_label"] == "发生时间未明确"
    assert indexed[unknown.id]["event_at"] is None
    assert indexed[year.id]["source_count"] == 1
    assert indexed[year.id]["recorded_at"] != indexed[year.id]["event_at"]
    assert (
        clients[0].get(f"/api/v1/memories/{year.id}/sources").json()["items"][0]["id"] == source.id
    )
    assert db.scalar(select(ModelUsage)) is None


def test_keyset_pagination_is_stable_with_equal_time_anchors(db, accounts, clients):
    expected = set()
    for i in range(7):
        fact, _, _ = remember(
            db,
            accounts[0][0],
            kind="travel",
            key="苏州",
            value=f"2019年合成旅行{i}",
            expression="2019年",
        )
        fact.recorded_at = datetime(2026, 1, 1)
        expected.add(fact.id)
    db.flush()
    seen, cursor = [], None
    while True:
        response = clients[0].get(
            "/api/v1/memories/timeline?limit=2" + (f"&before_id={cursor}" if cursor else "")
        )
        assert response.status_code == 200
        page = response.json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 7 and set(seen) == expected


def test_timeline_does_not_expose_another_user_deleted_mock_or_untraceable_facts(
    db, accounts, clients, monkeypatch
):
    own, _, _ = remember(db, accounts[0][0])
    foreign, _, _ = remember(db, accounts[1][0])
    removed, _, _ = remember(db, accounts[0][0], value="应该看不到的已删除记忆")
    removed.deleted_at = datetime(2026, 1, 1)
    db.add(MemoryFact(user_id=own.user_id, kind="event", key="无来源", value="不可展示"))
    db.flush()
    page = clients[0].get("/api/v1/memories/timeline").json()
    assert [m["id"] for m in page["items"]] == [own.id]
    assert clients[0].get(f"/api/v1/memories/timeline?before_id={foreign.id}").status_code == 404
    assert clients[0].get(f"/api/v1/memories/timeline?before_id={removed.id}").status_code == 404
    own.extractor_provider = "deepseek"
    db.flush()
    assert clients[0].get("/api/v1/memories/timeline").json()["items"] == []


def test_correction_and_soft_delete_immediately_change_the_derived_event_view(
    db, accounts, clients
):
    fact, _, _ = remember(db, accounts[0][0])
    response = clients[0].post(
        f"/api/v1/memories/{fact.id}/correct",
        json={
            "expected_revision": 1,
            "kind": "health",
            "key": "膝盖",
            "value": "我的膝盖已经好了",
            "time_expression": "2020年",
        },
    )
    assert response.status_code == 200
    rows = clients[0].get("/api/v1/memories/timeline").json()["items"]
    assert rows[0]["value"] == "我的膝盖已经好了" and rows[0]["event_label"] == "2020年"
    assert rows[0]["value_origin"] == "user_edit"
    assert (
        clients[0]
        .request("DELETE", f"/api/v1/memories/{fact.id}", json={"expected_revision": 2})
        .status_code
        == 200
    )
    assert clients[0].get("/api/v1/memories/timeline").json()["items"] == []
    assert db.scalar(select(MemorySource)) is not None


def test_source_count_is_owned_and_counts_distinct_actual_sources(db, accounts, clients):
    fact, _, _ = remember(db, accounts[0][0])
    _, second_source, _ = remember(db, accounts[0][0], value="我再次说明膝盖受伤")
    second_source.memory_id = fact.id
    db.flush()
    rows = clients[0].get("/api/v1/memories/timeline").json()["items"]
    assert len(rows) == 1 and rows[0]["source_count"] == 2
