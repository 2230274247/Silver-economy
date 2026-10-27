from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.errors import ApiError
from app.core.security import CurrentUser, DatabaseSession
from app.models.entities import Conversation, TaskDraft
from app.schemas.tasks import TaskDraftAction, TaskDraftOut, TaskDraftPage, TaskDraftPatch
from app.tasks.repository import act_on_draft, draft_data, owned_draft, update_draft

router = APIRouter(prefix="/api/v1")


@router.get("/task-drafts", response_model=TaskDraftPage)
def list_drafts(
    conversation_id: str,
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(30, ge=1, le=100),
):
    if not db.scalar(
        select(Conversation.id).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    ):
        raise ApiError(404, "NOT_FOUND", "会话不存在或无法访问")
    rows = db.scalars(
        select(TaskDraft)
        .where(TaskDraft.user_id == user.id, TaskDraft.conversation_id == conversation_id)
        .order_by(TaskDraft.created_at.desc(), TaskDraft.id.desc())
        .limit(limit)
    ).all()
    return {"items": [draft_data(row) for row in rows]}


@router.get("/task-drafts/{draft_id}", response_model=TaskDraftOut)
def get_draft(draft_id: str, user: CurrentUser, db: DatabaseSession):
    return draft_data(owned_draft(db, user.id, draft_id))


@router.post("/task-drafts/{draft_id}/edit", response_model=TaskDraftOut)
def patch_draft(draft_id: str, payload: TaskDraftPatch, user: CurrentUser, db: DatabaseSession):
    return update_draft(db, user.id, draft_id, payload)


@router.post("/task-drafts/{draft_id}/actions", response_model=TaskDraftOut)
def draft_action(draft_id: str, payload: TaskDraftAction, user: CurrentUser, db: DatabaseSession):
    return act_on_draft(db, user.id, draft_id, payload)
