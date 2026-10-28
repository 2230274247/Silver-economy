from fastapi import APIRouter, Query

from app.core.security import CurrentUser, DatabaseSession
from app.schemas.tasks import (
    OutingTaskAction,
    OutingTaskFeedback,
    OutingTaskOut,
    OutingTaskPage,
    OutingTaskPatch,
    ProactiveUpdatePreference,
    ScheduleConfirm,
    SchedulePreviewRequest,
    TaskDraftOut,
)
from app.tasks import scheduling

router = APIRouter(prefix="/api/v1")


@router.post("/outing-tasks/{task_id}/replacement-draft", response_model=TaskDraftOut)
def replacement_draft(
    task_id: str, payload: OutingTaskAction, user: CurrentUser, db: DatabaseSession
):
    return scheduling.create_replacement_draft(db, user.id, task_id, payload)


@router.post("/task-drafts/{draft_id}/schedule-preview", response_model=TaskDraftOut)
def schedule_preview(
    draft_id: str,
    payload: SchedulePreviewRequest,
    user: CurrentUser,
    db: DatabaseSession,
):
    return scheduling.schedule_preview(db, user.id, draft_id, payload)


@router.post("/task-drafts/{draft_id}/schedule", response_model=OutingTaskOut, status_code=201)
def schedule_task(draft_id: str, payload: ScheduleConfirm, user: CurrentUser, db: DatabaseSession):
    return scheduling.confirm_schedule(db, user.id, draft_id, payload)


@router.get("/outing-tasks", response_model=OutingTaskPage)
def list_tasks(
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(100, ge=1, le=200),
):
    return scheduling.list_tasks(db, user.id, limit)


@router.get("/outing-tasks/{task_id}", response_model=OutingTaskOut)
def get_task(task_id: str, user: CurrentUser, db: DatabaseSession):
    return scheduling.task_data(db, scheduling.owned_task(db, user.id, task_id))


@router.patch("/outing-tasks/{task_id}", response_model=OutingTaskOut)
def update_task(task_id: str, payload: OutingTaskPatch, user: CurrentUser, db: DatabaseSession):
    return scheduling.update_task(db, user.id, task_id, payload)


@router.post("/outing-tasks/{task_id}/cancel", response_model=OutingTaskOut)
def cancel_task(task_id: str, payload: OutingTaskAction, user: CurrentUser, db: DatabaseSession):
    return scheduling.transition_task(db, user.id, task_id, payload, "cancelled")


@router.post("/outing-tasks/{task_id}/complete", response_model=OutingTaskOut)
def complete_task(task_id: str, payload: OutingTaskAction, user: CurrentUser, db: DatabaseSession):
    return scheduling.transition_task(db, user.id, task_id, payload, "completed")


@router.post("/outing-tasks/{task_id}/depart", response_model=OutingTaskOut)
def depart_task(task_id: str, payload: OutingTaskAction, user: CurrentUser, db: DatabaseSession):
    return scheduling.depart_task(db, user.id, task_id, payload)


@router.get("/outing-tasks/{task_id}/status", response_model=OutingTaskOut)
def task_status(task_id: str, user: CurrentUser, db: DatabaseSession):
    return scheduling.task_data(db, scheduling.owned_task(db, user.id, task_id))


@router.post("/outing-tasks/{task_id}/feedback", response_model=OutingTaskOut)
def task_feedback(
    task_id: str,
    payload: OutingTaskFeedback,
    user: CurrentUser,
    db: DatabaseSession,
):
    return scheduling.record_feedback(db, user.id, task_id, payload)


@router.patch("/outing-tasks/{task_id}/proactive-updates", response_model=OutingTaskOut)
def proactive_updates(
    task_id: str,
    payload: ProactiveUpdatePreference,
    user: CurrentUser,
    db: DatabaseSession,
):
    return scheduling.set_proactive_preference(db, user.id, task_id, payload)
