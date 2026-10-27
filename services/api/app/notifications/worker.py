"""Independent MySQL-backed notification Worker.

Run once:
    python -m app.notifications.worker --once

This Worker does not depend on a webpage or FastAPI being alive.
"""

import argparse
import logging
import os
import socket
import time
import uuid
from datetime import timedelta

from sqlalchemy import or_, select, update

from app.core.config import get_settings
from app.core.database import session_factory
from app.core.security import utc_now
from app.models.entities import NotificationJob, OutingTask, Reminder, TaskAuditLog
from app.notifications.providers import NotificationFailure, get_notification_provider

logger = logging.getLogger("silver.worker")


def default_owner():
    return f"{socket.gethostname()}:{os.getpid()}"


def _audit(db, job, event_type, *, error_code=None):
    db.add(
        TaskAuditLog(
            user_id=job.user_id,
            outing_task_id=job.outing_task_id,
            event_type=event_type,
            actor="worker",
            task_revision=job.task_revision,
            payload={"job_id": job.id, "attempts": job.attempts, "error_code": error_code},
        )
    )


def recover_worker_state(db, *, now, grace_minutes):
    missed_before = now - timedelta(minutes=grace_minutes)
    expired = db.scalars(
        select(NotificationJob)
        .where(
            NotificationJob.status == "claimed",
            NotificationJob.lease_expires_at <= now,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in expired:
        job.status = "unknown"
        job.error_code = "LEASE_EXPIRED_UNKNOWN_OUTCOME"
        job.completed_at = now
        job.lease_owner = job.lease_token = job.lease_expires_at = None
        db.execute(
            update(Reminder)
            .where(Reminder.user_id == job.user_id, Reminder.id == job.reminder_id)
            .values(status="unknown")
        )
        _audit(db, job, "notification_unknown", error_code=job.error_code)

    missed = db.scalars(
        select(NotificationJob)
        .where(
            NotificationJob.status.in_(["queued", "retry_scheduled"]),
            NotificationJob.scheduled_at < missed_before,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in missed:
        job.status = "missed"
        job.error_code = "DELIVERY_WINDOW_EXPIRED"
        job.completed_at = now
        db.execute(
            update(Reminder)
            .where(Reminder.user_id == job.user_id, Reminder.id == job.reminder_id)
            .values(status="expired")
        )
        _audit(db, job, "notification_missed", error_code=job.error_code)
    return {"recovered_unknown": len(expired), "missed": len(missed)}


def claim_due_jobs(db, *, now, owner, lease_seconds, limit):
    jobs = db.scalars(
        select(NotificationJob)
        .where(
            NotificationJob.status.in_(["queued", "retry_scheduled"]),
            NotificationJob.scheduled_at <= now,
            or_(
                NotificationJob.next_attempt_at.is_(None),
                NotificationJob.next_attempt_at <= now,
            ),
        )
        .order_by(NotificationJob.scheduled_at, NotificationJob.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()
    claims = []
    for job in jobs:
        token = str(uuid.uuid4())
        job.status = "claimed"
        job.attempts += 1
        job.lease_owner = owner
        job.lease_token = token
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.last_attempt_at = now
        claims.append((job.id, token))
    return claims


def _process_claim(factory, provider, job_id, token):
    with factory() as db:
        job = db.scalar(
            select(NotificationJob)
            .where(NotificationJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job is None or job.status != "claimed" or job.lease_token != token:
            return "lease_lost"
        task = db.scalar(
            select(OutingTask).where(
                OutingTask.user_id == job.user_id,
                OutingTask.id == job.outing_task_id,
            )
        )
        reminder = db.scalar(
            select(Reminder).where(
                Reminder.user_id == job.user_id,
                Reminder.id == job.reminder_id,
            )
        )
        if task is None or task.status != "scheduled":
            job.status = "cancelled"
            job.error_code = "TASK_NO_LONGER_ACTIVE"
            job.completed_at = utc_now()
            if reminder and reminder.status == "pending":
                reminder.status = "cancelled"
            _audit(db, job, "notification_cancelled", error_code=job.error_code)
            db.commit()
            return "cancelled"
        if task.revision != job.task_revision or reminder is None or reminder.status != "pending":
            job.status = "cancelled"
            job.error_code = "STALE_TASK_REVISION"
            job.completed_at = utc_now()
            _audit(db, job, "notification_cancelled", error_code=job.error_code)
            db.commit()
            return "cancelled"
        # Claim state is committed before external I/O, so a crash remains observable.
        db.commit()

    try:
        result = provider.send(task, job)
    except NotificationFailure as failure:
        with factory() as db:
            job = db.scalar(
                select(NotificationJob)
                .where(NotificationJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None or job.status != "claimed" or job.lease_token != token:
                return "lease_lost"
            now = utc_now()
            job.lease_owner = job.lease_token = job.lease_expires_at = None
            job.error_code = failure.code
            if failure.retryable and job.attempts < job.max_attempts:
                job.status = "retry_scheduled"
                job.next_attempt_at = now + timedelta(minutes=job.attempts)
                reminder_status = "retry_scheduled"
            else:
                job.status = "failed"
                job.completed_at = now
                reminder_status = "failed"
            db.execute(
                update(Reminder)
                .where(Reminder.user_id == job.user_id, Reminder.id == job.reminder_id)
                .values(status=reminder_status)
            )
            _audit(db, job, "notification_failed", error_code=failure.code)
            db.commit()
            return job.status
    except Exception:
        # A timeout or process fault after the provider boundary is outcome-unknown.
        with factory() as db:
            job = db.scalar(
                select(NotificationJob)
                .where(NotificationJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None or job.status != "claimed" or job.lease_token != token:
                return "lease_lost"
            job.status = "unknown"
            job.error_code = "PROVIDER_OUTCOME_UNKNOWN"
            job.completed_at = utc_now()
            job.lease_owner = job.lease_token = job.lease_expires_at = None
            db.execute(
                update(Reminder)
                .where(Reminder.user_id == job.user_id, Reminder.id == job.reminder_id)
                .values(status="unknown")
            )
            _audit(db, job, "notification_unknown", error_code=job.error_code)
            db.commit()
            return "unknown"

    with factory() as db:
        job = db.scalar(
            select(NotificationJob)
            .where(NotificationJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job is None or job.status != "claimed" or job.lease_token != token:
            return "lease_lost"
        job.status = "submitted_to_provider"
        job.provider_message_id = result["provider_message_id"]
        job.error_code = None
        job.lease_owner = job.lease_token = job.lease_expires_at = None
        db.execute(
            update(Reminder)
            .where(Reminder.user_id == job.user_id, Reminder.id == job.reminder_id)
            .values(status="submitted_to_provider")
        )
        _audit(db, job, "notification_submitted")
        db.commit()
        return "submitted"


def process_once(*, factory=None, provider=None, now=None, owner=None, limit=20):
    settings = get_settings()
    factory = factory or session_factory()
    provider = provider or get_notification_provider(settings)
    now = now or utc_now()
    owner = owner or default_owner()
    with factory() as db:
        recovered = recover_worker_state(
            db, now=now, grace_minutes=settings.worker_delivery_grace_minutes
        )
        claims = claim_due_jobs(
            db,
            now=now,
            owner=owner,
            lease_seconds=settings.worker_lease_seconds,
            limit=limit,
        )
        db.commit()
    outcomes = [_process_claim(factory, provider, job_id, token) for job_id, token in claims]
    return {
        **recovered,
        "claimed": len(claims),
        "submitted": outcomes.count("submitted"),
        "unknown": outcomes.count("unknown"),
        "failed": outcomes.count("failed"),
        "cancelled": outcomes.count("cancelled"),
        "lease_lost": outcomes.count("lease_lost"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Silver-economy durable notification worker")
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s UTC %(levelname)s %(name)s %(message)s",
    )
    while True:
        logger.info("scan %s", process_once(limit=args.limit))
        if args.once:
            return
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
