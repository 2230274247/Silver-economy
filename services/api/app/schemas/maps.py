from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DraftVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class LocationConsent(DraftVersion):
    enabled: bool


class PlaceSearch(DraftVersion):
    client_request_id: UUID
    field: Literal["origin", "destination"]
    query: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=40)
    search_kind: Literal["poi", "address"] = "poi"

    @field_validator("query", "city")
    @classmethod
    def nonblank(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Provide a city and a specific location")
        return value.strip()


class PlaceSelection(DraftVersion):
    field: Literal["origin", "destination"]
    query_id: UUID
    candidate_id: UUID


class MapPreview(DraftVersion):
    client_request_id: UUID


class MapsStatus(BaseModel):
    provider: Literal["disabled", "mock", "amap"]
    configured: bool
    live_connection_verified: Literal[False] = False


class PlaceCandidate(BaseModel):
    id: UUID
    name: str
    address: str
    district: str
    location: str
    adcode: str
    citycode: str
    level: str
    vendor_id: str


class PlaceSearchOut(BaseModel):
    query_id: UUID
    items: list[PlaceCandidate] = Field(max_length=5)
    provider: Literal["mock", "amap"]
    is_synthetic: bool
    fetched_at: datetime
    expires_at: datetime
