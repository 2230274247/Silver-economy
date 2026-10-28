from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.tasks.time_parse import parse_target

NEW_YORK = ZoneInfo("America/New_York")


def test_hong_kong_and_another_iana_zone_apply_the_correct_offsets():
    reference = datetime(2026, 7, 1, 12)

    hong_kong = parse_target("2026-07-02", "10:00", "", reference)
    summer_new_york = parse_target("2026-07-02", "10:00", "", reference, NEW_YORK)
    winter_new_york = parse_target("2026-01-15", "10:00", "", reference, NEW_YORK)

    assert hong_kong == datetime(2026, 7, 2, 2)
    assert summer_new_york == datetime(2026, 7, 2, 14)
    assert winter_new_york == datetime(2026, 1, 15, 15)


def test_dst_nonexistent_and_ambiguous_local_times_require_clarification():
    reference = datetime(2026, 1, 1, 12)

    assert parse_target("2026-03-08", "02:30", "", reference, NEW_YORK) is None
    assert parse_target("2026-11-01", "01:30", "", reference, NEW_YORK) is None


def test_calculation_uses_task_timezone_for_forecast_date():
    from app.tasks.scheduling import calculation

    target = datetime(2026, 7, 2, 2, 0, tzinfo=UTC).replace(tzinfo=None)
    value = calculation(
        kind="outing",
        time_semantics="arrival",
        target_at=target,
        map_snapshot={
            "route": {"duration_seconds": 1800},
            "weather": {
                "status": "available",
                "date": "2026-07-01",
                "umbrella_advice": "Synthetic",
            },
            "expires_at": "2026-07-02T01:55:00+00:00",
        },
        access_buffer_minutes=0,
        contingency_buffer_minutes=0,
        lead_minutes=0,
        now=datetime(2026, 7, 1, 20),
        timezone="America/New_York",
    )

    assert value["weather_reference_status"] == "available"
    assert value["weather_advice"] == "Synthetic"
