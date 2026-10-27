import json
import logging
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.security import utc_now
from app.maps import service
from app.maps.providers import AmapProvider, MapFailure, MockMapProvider, coordinate
from app.models.entities import MapBudget, MapRequest, ModelUsage, Reminder
from app.tasks.time_parse import ZONE
from tests.test_task_drafts import patch_fields, send


def key():
    return str(uuid.uuid4())


def created(a):
    _, result = send(a, "明天上午十点到张阿姨家，从我家出发，打车，提醒我")
    return result["assistant_message"]["task_drafts"][0]


def enable(a, draft):
    response = a.post(
        f"/api/v1/task-drafts/{draft['id']}/location-consent",
        json={"expected_revision": draft["revision"], "enabled": True},
    )
    assert response.status_code == 200
    return response.json()


def search(a, draft, field="origin", client_key=None):
    return a.post(
        f"/api/v1/task-drafts/{draft['id']}/places/search",
        json={
            "expected_revision": draft["revision"],
            "client_request_id": client_key or key(),
            "field": field,
            "query": "合成公园",
            "city": "北京",
        },
    )


def selected(a, draft, field):
    data = search(a, draft, field).json()
    response = a.post(
        f"/api/v1/task-drafts/{draft['id']}/places/select",
        json={
            "expected_revision": draft["revision"],
            "field": field,
            "query_id": data["query_id"],
            "candidate_id": data["items"][1]["id"],
        },
    )
    assert response.status_code == 200
    return response.json()


def ready(a):
    draft = enable(a, created(a))
    return selected(a, selected(a, draft, "origin"), "destination")


def test_no_consent_or_foreign_user_cannot_query_select_or_change_permission(clients, db):
    a, b = clients
    draft = created(a)
    assert search(a, draft).status_code == 403
    assert search(b, draft).status_code == 404
    assert (
        b.post(
            f"/api/v1/task-drafts/{draft['id']}/location-consent",
            json={"expected_revision": 1, "enabled": True},
        ).status_code
        == 404
    )
    assert db.scalar(select(func.count()).select_from(MapRequest)) == 0
    assert a.get("/api/v1/maps-status").json()["provider"] == "mock"
    assert (
        b.post(
            f"/api/v1/task-drafts/{draft['id']}/map-preview",
            json={"expected_revision": 1, "client_request_id": key()},
        ).status_code
        == 404
    )


def test_candidates_are_explicit_owned_choices_and_survive_refresh(clients):
    a, b = clients
    draft = enable(a, created(a))
    result = search(a, draft).json()
    assert len(result["items"]) == 2 and result["is_synthetic"]
    current = a.get(f"/api/v1/task-drafts/{draft['id']}").json()
    assert current["origin_place"] is None  # Never choose the first suggestion implicitly.
    payload = {
        "expected_revision": draft["revision"],
        "field": "origin",
        "query_id": result["query_id"],
        "candidate_id": result["items"][1]["id"],
    }
    assert (
        b.post(f"/api/v1/task-drafts/{draft['id']}/places/select", json=payload).status_code == 404
    )
    assert (
        a.post(
            f"/api/v1/task-drafts/{draft['id']}/places/select",
            json={**payload, "field": "destination"},
        ).status_code
        == 409
    )
    chosen = a.post(f"/api/v1/task-drafts/{draft['id']}/places/select", json=payload).json()
    assert chosen["origin_place"]["id"] == result["items"][1]["id"]
    assert a.get(f"/api/v1/task-drafts/{draft['id']}").json() == chosen


def test_search_idempotency_and_same_query_cache_call_provider_once(clients, monkeypatch):
    a, _ = clients
    draft = enable(a, created(a))
    calls = []
    original = MockMapProvider.search
    monkeypatch.setattr(
        MockMapProvider,
        "search",
        lambda self, *args: (calls.append(args), original(self, *args))[1],
    )
    token = key()
    first = search(a, draft, client_key=token).json()
    assert search(a, draft, client_key=token).json() == first
    assert search(a, draft).json()["items"] == first["items"]
    assert len(calls) == 1


def test_preview_has_units_source_weather_persistence_and_no_new_model_or_job(clients, db):
    a, _ = clients
    draft = ready(a)
    before = db.scalar(select(func.count()).select_from(ModelUsage))
    payload = {"expected_revision": draft["revision"], "client_request_id": key()}
    response = a.post(f"/api/v1/task-drafts/{draft['id']}/map-preview", json=payload)
    assert response.status_code == 200
    value = response.json()
    snapshot = value["map_snapshot"]
    assert snapshot["route"]["distance_m"] == 12000
    assert snapshot["route"]["duration_seconds"] == 2100
    assert snapshot["weather"]["status"] == "available"
    assert "Mock" in snapshot["weather"]["umbrella_advice"] and snapshot["is_synthetic"]
    assert snapshot["scheduling_status"] == "not_scheduled"
    assert a.get(f"/api/v1/task-drafts/{draft['id']}").json()["map_snapshot"] == snapshot
    assert (
        a.post(f"/api/v1/task-drafts/{draft['id']}/map-preview", json=payload).json()[
            "map_snapshot"
        ]
        == snapshot
    )
    assert db.scalar(select(func.count()).select_from(ModelUsage)) == before
    assert db.scalar(select(func.count()).select_from(Reminder)) == 0


def test_editing_or_natural_followup_invalidates_snapshot_and_changed_place(clients):
    a, _ = clients
    draft = ready(a)
    value = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    ).json()
    edited = a.post(
        f"/api/v1/task-drafts/{draft['id']}/edit",
        json=patch_fields(value, origin="另一个出发地", destination=value["destination"]),
    ).json()
    assert edited["map_snapshot"] is None and edited["origin_place"] is None
    assert edited["destination_place"] is not None


def test_withdrawal_purges_cached_locations_and_denies_replay(clients, db):
    a, _ = clients
    draft = ready(a)
    result = a.post(
        f"/api/v1/task-drafts/{draft['id']}/location-consent",
        json={"expected_revision": draft["revision"], "enabled": False},
    ).json()
    assert not result["location_consent"]
    assert result["origin_place"] is result["destination_place"] is result["map_snapshot"] is None
    assert all(r.result is None and r.status == "revoked" for r in db.scalars(select(MapRequest)))
    assert search(a, result).status_code == 403
    enabled = enable(a, result)
    assert search(a, enabled).status_code == 200


def test_provider_failure_does_not_invent_route_or_query_weather(clients, monkeypatch):
    a, _ = clients
    draft = ready(a)
    calls = []

    def fail(*args):
        calls.append(True)
        raise MapFailure("MAP_TIMEOUT")

    monkeypatch.setattr(MockMapProvider, "route", fail)
    monkeypatch.setattr(
        MockMapProvider,
        "weather",
        lambda *args: pytest.fail("Do not spend weather quota after route failure"),
    )
    url = f"/api/v1/task-drafts/{draft['id']}/map-preview"
    for _ in range(2):
        data = a.post(
            url, json={"expected_revision": draft["revision"], "client_request_id": key()}
        ).json()
        assert data["map_snapshot"]["route"]["status"] == "unavailable"
        assert "duration_seconds" not in data["map_snapshot"]["route"]
    assert len(calls) == 1


def test_consent_withdrawn_during_query_discards_response(clients, db, monkeypatch):
    a, _ = clients
    draft = enable(a, created(a))
    original = MockMapProvider.search

    def withdraw(self, *args):
        a.post(
            f"/api/v1/task-drafts/{draft['id']}/location-consent",
            json={"expected_revision": draft["revision"], "enabled": False},
        )
        return original(self, *args)

    monkeypatch.setattr(MockMapProvider, "search", withdraw)
    response = search(a, draft)
    assert response.status_code == 409
    assert all(row.result is None for row in db.scalars(select(MapRequest)))


def test_real_provider_budget_rejects_before_transport(clients, db, monkeypatch):
    a, _ = clients
    draft = enable(a, created(a))
    monkeypatch.setenv("MAPS_PROVIDER", "amap")
    monkeypatch.setenv("AMAP_WEB_SERVICE_KEY", "synthetic-not-a-key")
    monkeypatch.setenv("AMAP_DAILY_REQUEST_LIMIT", "0")
    get_settings.cache_clear()
    monkeypatch.setattr(
        AmapProvider, "search", lambda *args: pytest.fail("Budget must reject first")
    )
    assert search(a, draft).json()["error"]["code"] == "MAP_BUDGET_EXCEEDED"
    assert db.scalar(select(func.count()).select_from(MapRequest)) == 0
    assert not db.scalar(select(MapBudget.requests))


def test_quota_is_shared_between_users_and_cache_does_not_charge_again(clients, db, monkeypatch):
    class BudgetedMock(MockMapProvider):
        name = "amap"

    monkeypatch.setenv("MAPS_PROVIDER", "amap")
    monkeypatch.setenv("AMAP_DAILY_REQUEST_LIMIT", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(service, "get_maps_provider", lambda _: BudgetedMock())
    a, b = clients
    first, other = enable(a, created(a)), enable(b, created(b))
    assert search(a, first).status_code == 200
    assert search(a, first).status_code == 200
    assert search(b, other).json()["error"]["code"] == "MAP_BUDGET_EXCEEDED"
    assert db.scalar(select(MapBudget.requests)) == 1


def test_deferred_task_still_allows_privacy_withdrawal(clients):
    a, _ = clients
    draft = ready(a)
    deferred = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "defer"},
    ).json()
    value = a.post(
        f"/api/v1/task-drafts/{draft['id']}/location-consent",
        json={"expected_revision": deferred["revision"], "enabled": False},
    ).json()
    assert value["status"] == "deferred" and not value["location_consent"]


def test_foreign_query_wrong_candidate_and_untrusted_coordinates_are_rejected(clients):
    a, b = clients
    first, other = enable(a, created(a)), enable(b, created(b))
    lookup = search(a, first).json()
    url = f"/api/v1/task-drafts/{other['id']}/places/select"
    payload = {
        "expected_revision": other["revision"],
        "field": "origin",
        "query_id": lookup["query_id"],
        "candidate_id": lookup["items"][0]["id"],
    }
    assert b.post(url, json=payload).status_code == 404
    assert b.post(url, json={**payload, "location": "0,0"}).status_code == 422


def test_expired_preview_is_explicit_and_information_confirmation_does_not_hide_it(
    clients, monkeypatch
):
    a, _ = clients
    draft = ready(a)
    value = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    ).json()
    assert value["map_snapshot"]["expired"] is False
    confirmed = a.post(
        f"/api/v1/task-drafts/{draft['id']}/actions",
        json={"expected_revision": draft["revision"], "action": "confirm"},
    ).json()
    assert confirmed["map_snapshot"]["draft_revision"] == confirmed["revision"]
    from app.tasks import repository

    before = utc_now()
    monkeypatch.setattr(repository, "utc_now", lambda: before + timedelta(minutes=16))
    assert a.get(f"/api/v1/task-drafts/{draft['id']}").json()["map_snapshot"]["expired"] is True


def amap(handle):
    return AmapProvider(
        Settings(
            _env_file=None, amap_web_service_key="synthetic-private-key", maps_provider="amap"
        ),
        httpx.MockTransport(handle),
    )


def test_official_search_bounds_and_drops_missing_coordinates_and_broad_regions(caplog):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.host == "restapi.amap.com"
        assert request.url.params["offset"] == "5" and request.url.params["citylimit"] == "true"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {"name": "无坐标", "adcode": "110101", "location": []},
                    {
                        "name": "合成门口",
                        "location": "116.4,39.9",
                        "adcode": "110101",
                        "citycode": "010",
                        "address": "合成1号",
                    },
                ],
            },
        )

    with caplog.at_level(logging.INFO):
        result = amap(handle).search("合成门口", "北京", "poi")
    assert len(result["items"]) == 1 and len(calls) == 1
    assert "synthetic-private-key" not in caplog.text
    empty = amap(
        lambda _: httpx.Response(
            200,
            json={
                "status": "1",
                "geocodes": [
                    {
                        "level": "市",
                        "formatted_address": "北京市",
                        "location": "116.4,39.9",
                        "adcode": "110000",
                    }
                ],
            },
        )
    ).search("合成地址", "北京", "address")
    assert empty["items"] == []


@pytest.mark.parametrize(
    "mode,path",
    [
        ("taxi", "driving"),
        ("driving", "driving"),
        ("walking", "walking"),
        ("cycling", "bicycling"),
        ("transit", "transit/integrated"),
    ],
)
def test_official_route_mode_cost_units_and_city_fields(mode, path):
    def handle(request):
        assert request.url.path == "/v5/direction/" + path
        assert request.url.params["show_fields"] == "cost"
        if mode == "transit":
            assert request.url.params["city1"] == request.url.params["city2"] == "010"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "route": {
                    "transits" if mode == "transit" else "paths": [
                        {"distance": "1234", "cost": {"duration": "345.2"}}
                    ]
                },
            },
        )

    place = {"location": "116.400000,39.900000", "citycode": "010"}
    result = amap(handle).route(place, place, mode)
    assert result["distance_m"] == 1234 and result["duration_seconds"] == 346


def test_forecast_uses_requested_day_region_reporttime_and_unknown_outside_range():
    day = datetime.now(ZONE).date().isoformat()

    def handle(request):
        assert request.url.path == "/v3/weather/weatherInfo"
        assert request.url.params["extensions"] == "all"
        return httpx.Response(
            200,
            json={
                "status": "1",
                "forecasts": [
                    {
                        "city": "合成区",
                        "adcode": "110101",
                        "reporttime": datetime.now(ZONE).strftime("%Y-%m-%d %H:%M:%S"),
                        "casts": [{"date": day, "dayweather": "小雨", "nightweather": "晴"}],
                    }
                ],
            },
        )

    provider = amap(handle)
    assert "建议带伞" in provider.weather({"adcode": "110101"}, day)["umbrella_advice"]
    assert provider.weather({"adcode": "110101"}, "2099-01-01")["reason"] == "MAP_OUT_OF_FORECAST"


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_official_errors_do_not_retry_or_expose_vendor_body(status):
    calls = []

    def handle(request):
        calls.append(True)
        return httpx.Response(status, text="synthetic-private-key")

    with pytest.raises(MapFailure) as error:
        amap(handle).search("合成地址", "北京", "poi")
    assert len(calls) == 1 and "synthetic-private-key" not in str(error.value)


@pytest.mark.parametrize("value", ["NaN,10", "181,10", "116,91", [], "116,39,1"])
def test_invalid_coordinates_are_not_accepted(value):
    with pytest.raises((ValueError, TypeError)):
        coordinate(value)


def test_weather_failure_keeps_route_but_never_invents_umbrella_advice(clients, monkeypatch):
    a, _ = clients
    draft = ready(a)

    def fail(*args):
        raise MapFailure("MAP_PROVIDER_ERROR")

    monkeypatch.setattr(MockMapProvider, "weather", fail)
    result = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    ).json()["map_snapshot"]
    assert result["route"]["duration_seconds"] == 2100
    assert (
        result["weather"]["status"] == "unavailable" and "umbrella_advice" not in result["weather"]
    )


def test_disabled_service_has_no_query_receipt_and_no_exposed_key(clients, db, monkeypatch):
    a, _ = clients
    draft = enable(a, created(a))
    monkeypatch.setenv("MAPS_PROVIDER", "disabled")
    get_settings.cache_clear()
    status = a.get("/api/v1/maps-status").json()
    assert status["configured"] is False and "key" not in json.dumps(status).lower()
    assert search(a, draft).json()["error"]["code"] == "MAP_NOT_CONFIGURED"
    assert db.scalar(select(func.count()).select_from(MapRequest)) == 0


def test_reserved_receipt_survives_restart_without_another_provider_call(clients, db, monkeypatch):
    a, _ = clients
    draft = enable(a, created(a))
    data = search(a, draft).json()
    record = db.get(MapRequest, data["query_id"])
    record.status, record.result = "reserved", None
    db.commit()
    monkeypatch.setattr(
        MockMapProvider,
        "search",
        lambda *args: pytest.fail("Do not replay an interrupted external request"),
    )
    assert search(a, draft).json()["error"]["code"] == "MAP_NETWORK_UNKNOWN"


def test_stale_weather_and_malformed_route_do_not_become_advice_or_measurements():
    old = (datetime.now(ZONE) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    provider = amap(
        lambda _: httpx.Response(
            200,
            json={
                "status": "1",
                "forecasts": [{"adcode": "110101", "reporttime": old, "casts": []}],
            },
        )
    )
    assert provider.weather({"adcode": "110101"}, "2026-10-28")["reason"] == "MAP_STALE_WEATHER"
    provider = amap(
        lambda _: httpx.Response(
            200,
            json={
                "status": "1",
                "route": {"paths": [{"distance": "1000", "cost": {"duration": "NaN"}}]},
            },
        )
    )
    with pytest.raises(MapFailure):
        provider.route({"location": "116,39"}, {"location": "116,40"}, "taxi")


def test_changed_after_route_does_not_spend_another_weather_query(clients, monkeypatch):
    a, _ = clients
    draft = ready(a)
    original = service.query

    def between_queries(db, current, client_key, operation, *args, **kwargs):
        result = original(db, current, client_key, operation, *args, **kwargs)
        if operation == "route":
            assert (
                a.post(
                    f"/api/v1/task-drafts/{draft['id']}/edit", json=patch_fields(draft)
                ).status_code
                == 200
            )
        return result

    monkeypatch.setattr(service, "query", between_queries)
    monkeypatch.setattr(
        MockMapProvider,
        "weather",
        lambda *args: pytest.fail("Changed draft must be rejected before another external query"),
    )
    response = a.post(
        f"/api/v1/task-drafts/{draft['id']}/map-preview",
        json={"expected_revision": draft["revision"], "client_request_id": key()},
    )
    assert response.status_code == 409
