"""When a scheduled workflow fires next: time zones, daylight saving, weekdays, month days, one-time runs."""

import datetime

import pytest

from evolvxsi.workflow_schedules import cadence

UTC = datetime.timezone.utc


def at(y, mo, d, h=0, mi=0):  # type: ignore[no-untyped-def]
    return datetime.datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_daily_fires_later_today_or_tomorrow() -> None:
    assert cadence.next_run("daily", "08:30", "UTC", None, None, None, at(2026, 11, 16, 7)) == at(2026, 11, 16, 8, 30)
    assert cadence.next_run("daily", "08:30", "UTC", None, None, None, at(2026, 11, 16, 8, 30)) == at(2026, 11, 17, 8, 30), "strictly after"


def test_wall_clock_time_survives_daylight_saving() -> None:
    # London: 08:30 is 08:30 UTC in winter and 07:30 UTC in summer.
    winter = cadence.next_run("daily", "08:30", "Europe/London", None, None, None, at(2026, 3, 28, 12))
    summer = cadence.next_run("daily", "08:30", "Europe/London", None, None, None, at(2026, 3, 29, 12))
    assert winter == at(2026, 3, 29, 7, 30) and summer == at(2026, 3, 30, 7, 30)
    assert cadence.next_run("daily", "08:30", "Europe/London", None, None, None, at(2026, 1, 10, 12)) == at(2026, 1, 11, 8, 30)


def test_weekdays_skip_the_weekend() -> None:
    friday_evening = at(2026, 11, 20, 20)  # a Friday
    assert cadence.next_run("weekdays", "09:00", "UTC", None, None, None, friday_evening) == at(2026, 11, 23, 9)  # Monday


def test_weekly_and_monthly() -> None:
    assert cadence.next_run("weekly", "09:00", "UTC", 2, None, None, at(2026, 11, 16)) == at(2026, 11, 18, 9)  # Wednesday
    assert cadence.next_run("monthly", "09:00", "UTC", None, 28, None, at(2026, 2, 28, 10)) == at(2026, 3, 28, 9)


def test_once_fires_once_then_never() -> None:
    day = datetime.date(2026, 12, 1)
    assert cadence.next_run("once", "10:00", "UTC", None, None, day, at(2026, 11, 30)) == at(2026, 12, 1, 10)
    assert cadence.next_run("once", "10:00", "UTC", None, None, day, at(2026, 12, 1, 10)) is None


def test_spread_moves_the_time_by_whole_minutes() -> None:
    assert cadence.next_run("daily", "08:30", "UTC", None, None, None, at(2026, 11, 16), spread_minutes=3) == at(2026, 11, 16, 8, 33)


def test_time_zone_offsets_are_applied() -> None:
    assert cadence.next_run("daily", "09:00", "Asia/Kolkata", None, None, None, at(2026, 11, 16)) == at(2026, 11, 16, 3, 30)


@pytest.mark.parametrize("args, message", [
    (("hourly", "08:00", "UTC", None, None, None), "Choose once"),
    (("daily", "8am", "UTC", None, None, None), "HH:MM"),
    (("daily", "25:00", "UTC", None, None, None), "HH:MM"),
    (("daily", "08:00", "Mars/Base", None, None, None), "time zone"),
    (("weekly", "08:00", "UTC", None, None, None), "day of the week"),
    (("monthly", "08:00", "UTC", None, 31, None), "1 to 28"),
    (("once", "08:00", "UTC", None, None, None), "date"),
])
def test_invalid_schedules_are_refused_with_a_reason(args, message) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(cadence.CadenceError, match=message):
        cadence.validate(*args)
