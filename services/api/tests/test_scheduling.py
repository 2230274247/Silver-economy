import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.core.security import utc_now
from app.maps.providers import MapFailure, MockMapProvider
from app.models.entities import (
    NotificationJob,
    OutingTask,
    Reminder,
    TaskAuditLog,
)
from app.notifications.worker import claim_due_jobs, process_once, recover_worker_state
from app.tasks.scheduling import calculation
from tests.test_maps import key
from tests.test_task_drafts import patch_fields, send

ZONE = ZoneInfo("Asia/Hong_Kong")


def schedule_ready(a, *, departure=False):
    text = (
        "明天上午十点从我家出发去张阿姨家，打车，提醒我"
        if departure
        else "明天上午十点到张阿姨家，从我家出发，打车，提醒我"
    )
    _, result = send(a, text)
    draft = result["assistant_message"]["task_drafts"][0]
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/location-consent",
        json={"expected_revision": draft["revision"], "enabled": True},
    ).json()
    from tests.test_maps import selected

    draft = selected(a, selected(a, draft, "origin"), "destination")
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    ).json()
    return a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "confirm"},
    ).json()


def preview(a, draft, access=10, contingency=15, lead=30, request=None):
    return a.post(
        f"/api/v1/task-drafts/{draft['id']}/schedule-preview",
        json={
            "expected_revision": draft["revision"],
            "client_request_id": request or key(),
            "access_buffer_minutes": access,
            "contingency_buffer_minutes": contingency,
            "lead_minutes": lead,
        },
    )


def confirm(a, draft, request):
    return a.post(
        f"/api/v1/task-drafts/{draft['id']}/schedule",
        json={
            "expected_revision": draft["revision"],
            "client_request_id": request,
            "access_buffer_minutes": draft["access_buffer_minutes"],
            "contingency_buffer_minutes": draft["contingency_buffer_minutes"],
            "lead_minutes": draft["lead_minutes"],
        },
    )


def local_clock(value):
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(ZONE)
        .strftime("%Y-%m-%d %H:%M")
    )


def test_arrival_uses_route_and_buffers_then_requires_separate_confirmation(clients, accounts, db):
    a, _ = clients
    draft = schedule_ready(a)
    assert draft["status"] == "confirmed"
    assert draft["scheduling_status"] == "not_scheduled"
    assert db.scalar(select(func.count()).select_from(OutingTask)) == 0
    previewed = preview(a, draft).json()
    assert previewed["schedule_preview"]["departure_at"].endswith("01:00:00+00:00")
    assert previewed["schedule_preview"]["reminder_at"].endswith("00:30:00+00:00")
    assert previewed["schedule_preview"]["formula"].startswith("arrival_at")
    assert db.scalar(select(func.count()).select_from(OutingTask)) == 0
    request = str(uuid.uuid4())
    response = a.post(
        f"/api/v1/task-drafts/{draft['id']}/schedule",
        json={
            "expected_revision": previewed["revision"],
            "client_request_id": request,
            "access_buffer_minutes": 10,
            "contingency_buffer_minutes": 15,
            "lead_minutes": 30,
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert local_clock(task["departure_at"]).endswith("09:00")
    assert local_clock(task["reminder_at"]).endswith("08:30")
    assert task["status"] == "scheduled" and task["notifications"][0]["status"] == "queued"
    assert task["notifications"][0]["is_mock"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(OutingTask)
            .where(OutingTask.user_id == accounts[0][0].id)
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == accounts[0][0].id)
        )
        == 1
    )
    repeated = a.post(
        f"/api/v1/task-drafts/{draft['id']}/schedule",
        json={
            "expected_revision": previewed["revision"],
            "client_request_id": request,
            "access_buffer_minutes": 10,
            "contingency_buffer_minutes": 15,
            "lead_minutes": 30,
        },
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == task["id"]
    assert db.scalar(select(func.count()).select_from(OutingTask)) == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(NotificationJob)
            .where(NotificationJob.payload["job_type"].as_string() == "reminder")
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(NotificationJob)
            .where(NotificationJob.payload["job_type"].as_string() == "internal_refresh")
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(TaskAuditLog)
            .where(TaskAuditLog.outing_task_id == task["id"])
        )
        == 1
    )
    assert a.get(f"/api/v1/task-drafts/{draft['id']}").json()["scheduling_status"] == "scheduled"


def test_departure_semantics_and_plain_reminder_never_subtract_route_twice(clients):
    a, _ = clients
    departure = schedule_ready(a, departure=True)
    previewed = preview(a, departure, access=30, contingency=30, lead=30).json()
    task = confirm(a, previewed, str(uuid.uuid4())).json()
    assert task["time_semantics"] == "departure"
    assert local_clock(task["target_at"]) == local_clock(task["departure_at"])
    assert local_clock(task["reminder_at"]).endswith("09:30")
    assert task["calculation_basis"]["route_subtracted"] is False

    _, result = send(a, "明天上午九点提醒我浇花")
    draft = result["assistant_message"]["task_drafts"][0]
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "confirm"},
    ).json()
    previewed = preview(a, draft, access=99, contingency=99, lead=15).json()
    task = confirm(a, previewed, str(uuid.uuid4())).json()
    assert task["kind"] == "reminder"
    assert task["route_snapshot"] is None and task["weather_snapshot"] is None
    assert local_clock(task["target_at"]) == local_clock(task["departure_at"])
    assert local_clock(task["reminder_at"]).endswith("08:45")
    assert task["calculation_basis"]["route_subtracted"] is False
    assert task["notifications"][0]["is_mock"]


def test_preview_rejects_incomplete_stale_and_past_schedules(clients, monkeypatch):
    a, _ = clients
    _, result = send(a, "明天上午十点去张阿姨家，提醒我")
    draft = result["assistant_message"]["task_drafts"][0]
    assert preview(a, draft).status_code == 409
    edited = a.post(
        f"/api/v1/task-drafts/{draft['id']}/edit",
        json=patch_fields(draft),
    ).json()
    confirmed = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": edited["revision"], "action": "confirm"},
    ).json()
    response = preview(a, confirmed)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ROUTE_REQUIRED_FOR_ARRIVAL"
    negative = a.post(
        f"/api/v1/task-drafts/{draft['id']}/schedule-preview",
        json={
            "expected_revision": confirmed["revision"],
            "client_request_id": str(uuid.uuid4()),
            "access_buffer_minutes": -1,
            "contingency_buffer_minutes": 15,
            "lead_minutes": 30,
        },
    )
    assert negative.status_code == 422
    with pytest.raises(ApiError) as error:
        calculation(
            kind="reminder",
            time_semantics="at",
            target_at=utc_now() - timedelta(minutes=1),
            map_snapshot=None,
            access_buffer_minutes=0,
            contingency_buffer_minutes=0,
            lead_minutes=0,
            now=utc_now(),
        )
    assert error.value.code == "TARGET_TIME_PAST"


def test_cross_midnight_and_year_calculation_is_deterministic():
    target = datetime(2027, 1, 1, 1, 30, tzinfo=ZONE).astimezone(UTC).replace(tzinfo=None)
    value = calculation(
        kind="outing",
        time_semantics="arrival",
        target_at=target,
        map_snapshot={
            "route": {"duration_seconds": 1800},
            "expires_at": "2027-01-01T00:05:00+00:00",
        },
        access_buffer_minutes=10,
        contingency_buffer_minutes=15,
        lead_minutes=30,
        now=datetime(2026, 12, 31, 15, 0),
    )
    assert value["departure_at"] == "2026-12-31T16:35:00+00:00"
    assert value["reminder_at"] == "2026-12-31T16:05:00+00:00"


def test_edit_cancel_complete_isolate_and_invalidate_future_jobs(clients, db):
    a, b = clients
    draft = schedule_ready(a)
    previewed = preview(a, draft).json()
    task = confirm(a, previewed, str(uuid.uuid4())).json()
    original_job = task["notifications"][0]["id"]
    new_target = (
        datetime.fromisoformat(task["target_at"].replace("Z", "+00:00")) + timedelta(days=1)
    ).isoformat()
    response = a.patch(
        f"/api/v1/outing-tasks/{task['id']}",
        json={
            "expected_revision": task["revision"],
            "title": "Synthetic 修改后的出行",
            "target_at": new_target,
            "access_buffer_minutes": 10,
            "contingency_buffer_minutes": 15,
            "lead_minutes": 30,
        },
    )
    assert response.status_code == 200
    changed = response.json()
    assert changed["revision"] == 2 and changed["title"] == "Synthetic 修改后的出行"
    old = db.get(NotificationJob, original_job)
    assert old.status == "cancelled"
    reminder_jobs = [job for job in changed["notifications"] if job["purpose"] == "reminder"]
    assert sorted((job["status"], job["provider_message_id"]) for job in reminder_jobs) == [
        ("cancelled", None),
        ("queued", None),
    ]
    assert sorted(
        job["status"] for job in changed["notifications"] if job["purpose"] == "internal_refresh"
    ) == ["cancelled", "queued"]
    assert b.get(f"/api/v1/outing-tasks/{task['id']}").status_code == 404
    assert b.get("/api/v1/outing-tasks").json()["items"] == []
    assert (
        b.post(
            f"/api/v1/outing-tasks/{task['id']}/cancel",
            json={"expected_revision": changed["revision"]},
        ).status_code
        == 404
    )
    cancelled = a.post(
        f"/api/v1/outing-tasks/{task['id']}/cancel",
        json={"expected_revision": changed["revision"]},
    ).json()
    assert cancelled["status"] == "cancelled"
    assert all(
        job["status"] == "cancelled"
        for job in cancelled["notifications"]
        if job["scheduled_at"] >= cancelled["confirmed_at"]
    )

    second = schedule_ready(a)
    second = preview(a, second).json()
    second_task = confirm(a, second, str(uuid.uuid4())).json()
    completed = a.post(
        f"/api/v1/outing-tasks/{second_task['id']}/complete",
        json={"expected_revision": second_task["revision"]},
    ).json()
    assert completed["status"] == "completed"
    assert completed["notifications"][0]["status"] == "cancelled"


def test_trip_detail_navigation_departure_completion_feedback_and_isolation(clients, db):
    a, b = clients
    draft = schedule_ready(a)
    previewed = preview(a, draft).json()
    task = confirm(a, previewed, str(uuid.uuid4())).json()
    assert task["navigation_url"].startswith("https://uri.amap.com/search?keyword=")
    assert task["departed_at"] is None

    detail = a.get(f"/api/v1/outing-tasks/{task['id']}/status")
    assert detail.status_code == 200
    assert detail.json()["id"] == task["id"]
    assert b.get(f"/api/v1/outing-tasks/{task['id']}/status").status_code == 404

    feedback = a.post(
        f"/api/v1/outing-tasks/{task['id']}/feedback",
        json={
            "expected_revision": task["revision"],
            "feedback": "helpful",
            "note": "Synthetic feedback",
        },
    )
    assert feedback.status_code == 200
    assert feedback.json()["revision"] == task["revision"]
    assert (
        b.post(
            f"/api/v1/outing-tasks/{task['id']}/feedback",
            json={"expected_revision": task["revision"], "feedback": "helpful"},
        ).status_code
        == 404
    )

    departed = a.post(
        f"/api/v1/outing-tasks/{task['id']}/depart",
        json={"expected_revision": task["revision"]},
    )
    assert departed.status_code == 200
    departed_task = departed.json()
    assert departed_task["status"] == "departed"
    assert departed_task["departed_at"] is not None
    assert departed_task["notifications"][0]["status"] == "cancelled"
    repeated = a.post(
        f"/api/v1/outing-tasks/{task['id']}/depart",
        json={"expected_revision": task["revision"]},
    )
    assert repeated.status_code == 200 and repeated.json()["revision"] == departed_task["revision"]
    assert (
        a.post(
            f"/api/v1/outing-tasks/{task['id']}/cancel",
            json={"expected_revision": departed_task["revision"]},
        ).status_code
        == 409
    )

    completed = a.post(
        f"/api/v1/outing-tasks/{task['id']}/complete",
        json={"expected_revision": departed_task["revision"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    events = db.scalars(
        select(TaskAuditLog.event_type).where(TaskAuditLog.outing_task_id == task["id"])
    ).all()
    assert "user_feedback" in events
    assert "task_departed" in events
    assert "task_completed" in events


def worker_factory(db):
    return lambda: nullcontext(db)


def make_due(db, a):
    _, result = send(a, "明天上午九点提醒我整理药盒")
    draft = result["assistant_message"]["task_drafts"][0]
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "confirm"},
    ).json()
    draft = preview(a, draft, lead=0).json()
    task = confirm(a, draft, str(uuid.uuid4())).json()
    job = db.get(NotificationJob, task["notifications"][0]["id"])
    job.scheduled_at = utc_now() - timedelta(minutes=1)
    reminder = db.get(Reminder, job.reminder_id)
    reminder.due_at = job.scheduled_at
    db.commit()
    return job, reminder


def test_worker_success_unknown_outcome_and_missed_window_never_replays(clients, db):
    a, _ = clients
    job, reminder = make_due(db, a)
    first = process_once(factory=worker_factory(db), owner="worker-a")
    assert first["submitted"] == 1
    assert job.status == "submitted_to_provider" and reminder.status == "submitted_to_provider"
    second = process_once(factory=worker_factory(db), owner="worker-b")
    assert second["claimed"] == 0

    unknown_job, unknown_reminder = make_due(db, a)

    class UnknownProvider:
        name = "mock"

        def send(self, task, item):
            raise RuntimeError("simulated timeout after provider boundary")

    result = process_once(
        factory=worker_factory(db),
        provider=UnknownProvider(),
        owner="worker-c",
    )
    assert result["unknown"] == 1
    assert unknown_job.status == "unknown"
    assert unknown_reminder.status == "unknown"
    calls = []

    class NeverCalled:
        name = "mock"

        def send(self, task, item):
            calls.append(item.id)

    process_once(factory=worker_factory(db), provider=NeverCalled(), owner="worker-d")
    assert calls == []

    missed_job, missed_reminder = make_due(db, a)
    missed_job.scheduled_at = utc_now() - timedelta(hours=1)
    db.commit()
    missed = process_once(factory=worker_factory(db), owner="worker-e")
    assert missed["missed"] >= 1
    assert missed_job.status == "missed" and missed_reminder.status == "expired"


def test_worker_claim_is_single_owner_and_expired_lease_is_unknown(clients, db):
    a, _ = clients
    job, _ = make_due(db, a)
    first = claim_due_jobs(
        db,
        now=utc_now(),
        owner="first",
        lease_seconds=60,
        limit=1,
    )
    second = claim_due_jobs(
        db,
        now=utc_now(),
        owner="second",
        lease_seconds=60,
        limit=1,
    )
    assert len(first) == 1 and second == []
    job.lease_expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    result = process_once(factory=worker_factory(db), owner="third")
    assert result["recovered_unknown"] >= 1
    assert job.status == "unknown"


def scheduled_outing(a):
    draft = schedule_ready(a)
    previewed = preview(a, draft).json()
    return confirm(a, previewed, str(uuid.uuid4())).json()


def due_refresh(db, task):
    job = next(
        db.get(NotificationJob, item["id"])
        for item in task["notifications"]
        if item["purpose"] == "internal_refresh"
    )
    job.scheduled_at = utc_now() - timedelta(minutes=1)
    db.commit()
    return job


@pytest.mark.parametrize("expired_lease", [False, True])
def test_refresh_recovery_does_not_expire_or_poison_primary_reminder(clients, db, expired_lease):
    a, _ = clients
    task = scheduled_outing(a)
    refresh = due_refresh(db, task)
    if expired_lease:
        refresh.status = "claimed"
        refresh.lease_expires_at = utc_now() - timedelta(seconds=1)
    else:
        refresh.scheduled_at = utc_now() - timedelta(hours=1)
    db.commit()
    recover_worker_state(db, now=utc_now(), grace_minutes=15)
    db.commit()
    assert refresh.status == ("unknown" if expired_lease else "missed")
    assert db.get(Reminder, refresh.reminder_id).status == "pending"


def test_explicit_provider_retry_reaches_a_second_attempt(clients, db):
    from app.notifications.providers import NotificationFailure

    a, _ = clients
    job, reminder = make_due(db, a)

    class BusyProvider:
        name = "mock"

        def send(self, task, item):
            raise NotificationFailure("PROVIDER_TEMPORARILY_UNAVAILABLE", retryable=True)

    assert process_once(factory=worker_factory(db), provider=BusyProvider())["claimed"] == 1
    assert job.status == "retry_scheduled"
    job.next_attempt_at = utc_now() - timedelta(seconds=1)
    db.commit()
    assert process_once(factory=worker_factory(db))["submitted"] == 1
    assert job.attempts == 2
    assert reminder.status == "submitted_to_provider"


def test_proactive_route_change_updates_once_notifies_and_keeps_primary_lifecycle(
    clients, db, monkeypatch
):
    a, _ = clients
    task = scheduled_outing(a)
    refresh_job = due_refresh(db, task)
    calls = []

    def changed_route(self, origin, destination, mode):
        calls.append(mode)
        return {
            "distance_m": 16000,
            "duration_seconds": 3000,
            "transport": mode,
            "estimate_basis": "Synthetic 路线变化测试",
        }

    monkeypatch.setattr(MockMapProvider, "route", changed_route)
    first = process_once(factory=worker_factory(db), owner="refresh-worker")
    assert first["submitted"] == 1
    assert refresh_job.status == "completed"
    changed = db.get(OutingTask, task["id"])
    assert changed.revision == 2
    assert changed.route_snapshot["duration_seconds"] == 3000
    assert changed.last_proactive_refresh_at is not None
    assert changed.proactive_refresh_at is None
    jobs = db.scalars(
        select(NotificationJob)
        .where(NotificationJob.outing_task_id == task["id"])
        .order_by(NotificationJob.created_at, NotificationJob.id)
    ).all()
    assert any(
        job.payload.get("job_type") == "schedule_change" and job.status == "queued" for job in jobs
    )
    active_primary = [
        job for job in jobs if job.payload.get("job_type") == "reminder" and job.status == "queued"
    ]
    assert len(active_primary) == 1
    assert calls == ["taxi"]

    second = process_once(factory=worker_factory(db), owner="change-worker")
    assert second["submitted"] == 1
    assert db.get(Reminder, active_primary[0].reminder_id).status == "pending"
    assert calls == ["taxi"]


def test_proactive_refresh_failure_preserves_primary_and_is_not_retried(clients, db, monkeypatch):
    a, _ = clients
    task = scheduled_outing(a)
    refresh_job = due_refresh(db, task)

    def unavailable(*args):
        raise MapFailure("MAP_TIMEOUT")

    monkeypatch.setattr(MockMapProvider, "route", unavailable)
    result = process_once(factory=worker_factory(db), owner="refresh-worker")
    assert result["failed"] == 1
    assert refresh_job.status == "failed"
    assert refresh_job.error_code == "MAP_TIMEOUT"
    active = db.scalars(
        select(NotificationJob).where(
            NotificationJob.outing_task_id == task["id"],
            NotificationJob.payload["job_type"].as_string() == "reminder",
        )
    ).all()
    assert len(active) == 1
    assert active[0].status == "queued"
    assert db.get(Reminder, active[0].reminder_id).status == "pending"
    assert process_once(factory=worker_factory(db), owner="second-worker")["claimed"] == 0


def test_proactive_weather_change_notifies_without_moving_explicit_schedule(
    clients, db, monkeypatch
):
    a, _ = clients
    task = scheduled_outing(a)
    refresh_job = due_refresh(db, task)

    def changed_weather(self, destination, day):
        return {
            "status": "available",
            "date": day,
            "city": "Synthetic示例区域",
            "adcode": destination["adcode"],
            "reporttime": utc_now().isoformat(),
            "dayweather": "晴（Synthetic）",
            "nightweather": "晴（Synthetic）",
            "umbrella_advice": "Mock示例：当前未提示雨雪",
        }

    monkeypatch.setattr(MockMapProvider, "weather", changed_weather)
    result = process_once(factory=worker_factory(db), owner="weather-worker")
    assert result["submitted"] == 1
    changed = db.get(OutingTask, task["id"])
    assert changed.revision == task["revision"]
    assert changed.departure_at == datetime.fromisoformat(
        task["departure_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)
    assert refresh_job.status == "completed"
    assert (
        db.scalar(
            select(func.count())
            .select_from(NotificationJob)
            .where(
                NotificationJob.outing_task_id == task["id"],
                NotificationJob.payload["job_type"].as_string() == "schedule_change",
            )
        )
        == 1
    )
    assert any(
        event == "proactive_refresh_updated"
        for event in db.scalars(
            select(TaskAuditLog.event_type).where(TaskAuditLog.outing_task_id == task["id"])
        )
    )


def test_proactive_preference_can_disable_and_reenable_without_touching_primary(clients, db):
    a, b = clients
    task = scheduled_outing(a)
    disabled = a.patch(
        f"/api/v1/outing-tasks/{task['id']}/proactive-updates",
        json={
            "expected_revision": task["revision"],
            "enabled": False,
            "change_threshold_minutes": 12,
        },
    )
    assert disabled.status_code == 200
    value = disabled.json()
    assert value["proactive_updates_enabled"] is False
    assert value["proactive_change_threshold_minutes"] == 12
    assert value["proactive_refresh_at"] is None
    assert (
        next(job for job in value["notifications"] if job["purpose"] == "reminder")["status"]
        == "queued"
    )
    assert (
        next(job for job in value["notifications"] if job["purpose"] == "internal_refresh")[
            "status"
        ]
        == "cancelled"
    )
    assert (
        b.patch(
            f"/api/v1/outing-tasks/{task['id']}/proactive-updates",
            json={
                "expected_revision": task["revision"],
                "enabled": True,
                "change_threshold_minutes": 10,
            },
        ).status_code
        == 404
    )

    enabled = a.patch(
        f"/api/v1/outing-tasks/{task['id']}/proactive-updates",
        json={
            "expected_revision": task["revision"],
            "enabled": True,
            "change_threshold_minutes": 10,
        },
    )
    assert enabled.status_code == 200
    refresh_statuses = sorted(
        job["status"]
        for job in enabled.json()["notifications"]
        if job["purpose"] == "internal_refresh"
    )
    assert refresh_statuses == ["cancelled", "queued"]


@pytest.mark.parametrize("duration,departure,expected", [(2400, False, 0), (3000, True, 1)])
def test_proactive_threshold_and_explicit_departure_are_respected(
    clients, db, monkeypatch, duration, departure, expected
):
    a, _ = clients
    draft = schedule_ready(a, departure=departure)
    task = confirm(a, preview(a, draft).json(), str(uuid.uuid4())).json()
    due_refresh(db, task)

    def route(self, origin, destination, mode):
        return {"duration_seconds": duration, "distance_m": 15000, "transport": mode}

    monkeypatch.setattr(MockMapProvider, "route", route)
    process_once(factory=worker_factory(db))
    changed = a.get(f"/api/v1/outing-tasks/{task['id']}").json()
    assert changed["departure_at"] == task["departure_at"]
    assert sum(j["purpose"] == "schedule_change" for j in changed["notifications"]) == expected


def test_proactive_refresh_queries_the_edited_target_day(clients, db, monkeypatch):
    a, _ = clients
    task = scheduled_outing(a)
    new_target = datetime.fromisoformat(task["target_at"]) + timedelta(days=1)
    updated = a.patch(
        f"/api/v1/outing-tasks/{task['id']}",
        json={
            "expected_revision": task["revision"],
            "title": task["title"],
            "target_at": new_target.isoformat(),
        },
    ).json()
    active = next(
        db.get(NotificationJob, item["id"])
        for item in updated["notifications"]
        if item["purpose"] == "internal_refresh" and item["status"] == "queued"
    )
    active.scheduled_at = utc_now() - timedelta(seconds=1)
    db.commit()
    days = []
    original = MockMapProvider.weather

    def weather(self, destination, day):
        days.append(day)
        return original(self, destination, day)

    monkeypatch.setattr(MockMapProvider, "weather", weather)
    process_once(factory=worker_factory(db))
    assert days == [new_target.astimezone(ZONE).date().isoformat()]


def test_location_replacement_is_owned_idempotent_and_cancels_old_jobs_only_on_confirmation(
    clients, db
):
    from tests.test_maps import enable, selected

    a, b = clients
    task = scheduled_outing(a)
    url = f"/api/v1/outing-tasks/{task['id']}/replacement-draft"
    payload = {"expected_revision": task["revision"]}
    assert b.post(url, json=payload).status_code == 404
    response = a.post(url, json=payload)
    assert response.status_code == 200
    draft = response.json()
    assert a.post(url, json=payload).json()["id"] == draft["id"]
    assert draft["location_consent"] is False and draft["map_snapshot"] is None
    assert a.get(f"/api/v1/outing-tasks/{task['id']}").json()["status"] == "scheduled"
    draft = selected(a, selected(a, enable(a, draft), "origin"), "destination")
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    ).json()
    draft = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "confirm"},
    ).json()
    draft = preview(a, draft).json()
    new = confirm(a, draft, key())
    assert new.status_code == 201
    assert new.json()["id"] != task["id"]
    old = a.get(f"/api/v1/outing-tasks/{task['id']}").json()
    assert old["status"] == "cancelled"
    assert all(j["status"] == "cancelled" for j in old["notifications"])
    assert (
        len(
            db.scalars(
                select(OutingTask).where(
                    OutingTask.user_id == db.get(OutingTask, task["id"]).user_id,
                    OutingTask.status == "scheduled",
                )
            ).all()
        )
        == 1
    )
