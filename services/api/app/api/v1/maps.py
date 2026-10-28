from fastapi import APIRouter

from app.core.config import get_settings
from app.core.security import CurrentUser, DatabaseSession
from app.maps import service
from app.schemas.maps import (
    LocationConsent,
    MapPreview,
    MapsStatus,
    PlaceSearch,
    PlaceSearchOut,
    PlaceSelection,
)
from app.schemas.tasks import TaskDraftOut

router = APIRouter(prefix="/api/v1")


@router.get("/maps-status", response_model=MapsStatus)
def maps_status(user: CurrentUser):
    settings = get_settings()
    return {
        "provider": settings.maps_provider,
        "configured": settings.maps_provider == "mock"
        or settings.maps_provider == "amap"
        and bool(settings.amap_web_service_key.get_secret_value().strip()),
        "live_connection_verified": False,
    }


@router.post("/task-drafts/{draft_id}/location-consent", response_model=TaskDraftOut)
def location_consent(
    draft_id: str, payload: LocationConsent, user: CurrentUser, db: DatabaseSession
):
    return service.consent(db, user.id, draft_id, payload)


@router.post("/task-drafts/{draft_id}/places/search", response_model=PlaceSearchOut)
def search_places(draft_id: str, payload: PlaceSearch, user: CurrentUser, db: DatabaseSession):
    return service.search(db, user.id, draft_id, payload)


@router.post("/task-drafts/{draft_id}/places/select", response_model=TaskDraftOut)
def select_place(draft_id: str, payload: PlaceSelection, user: CurrentUser, db: DatabaseSession):
    return service.select_place(db, user.id, draft_id, payload)


@router.post("/task-drafts/{draft_id}/map-preview", response_model=TaskDraftOut)
def map_preview(draft_id: str, payload: MapPreview, user: CurrentUser, db: DatabaseSession):
    return service.preview(db, user.id, draft_id, payload)
