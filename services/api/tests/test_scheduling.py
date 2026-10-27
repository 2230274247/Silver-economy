import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.core.security import utc_now
from app.models.entities import (
    NotificationJob,
    OutingTask,
    Reminder,
    TaskAuditLog,
)
from app.notifications.worker import claim_due_jobs, process_once
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
    assert db.scalar(select(func.count()).select_from(NotificationJob)) == 1
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
    jobs = [job for job in changed["notifications"]]
    assert sorted((job["status"], job["provider_message_id"]) for job in jobs) == [
        ("cancelled", None),
        ("queued", None),
    ]
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
