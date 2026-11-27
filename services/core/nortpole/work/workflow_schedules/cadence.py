"""When a schedule fires next. Pure; no database. Times are wall-clock times in the owner's time zone, so a daily
08:30 stays 08:30 across daylight-saving changes. Monthly days stop at 28 so every month has the day."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CADENCES = ("once", "daily", "weekdays", "weekly", "monthly")


class CadenceError(ValueError):
    """The message is safe to show."""


def validate(cadence: str, at_time: str, tz: str, weekday: int | None, month_day: int | None, run_on: datetime.date | None) -> None:
    if cadence not in CADENCES:
        raise CadenceError("Choose once, daily, weekdays, weekly or monthly.")
    try:
        h, m = (int(x) for x in at_time.split(":"))
        datetime.time(h, m)
    except (ValueError, TypeError):
        raise CadenceError("The time must be HH:MM, for example 08:30.") from None
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise CadenceError("Unknown time zone.") from None
    if cadence == "weekly" and (weekday is None or not 0 <= weekday <= 6):
        raise CadenceError("Choose a day of the week.")
    if cadence == "monthly" and (month_day is None or not 1 <= month_day <= 28):
        raise CadenceError("Choose a day of the month from 1 to 28.")
    if cadence == "once" and run_on is None:
        raise CadenceError("Choose the date.")


def next_run(cadence: str, at_time: str, tz: str, weekday: int | None, month_day: int | None, run_on: datetime.date | None,
             after: datetime.datetime, spread_minutes: int = 0) -> datetime.datetime | None:
    """The first firing time strictly after `after` (aware), in UTC; None when a one-time schedule has passed."""
    zone = ZoneInfo(tz)
    h, m = (int(x) for x in at_time.split(":"))
    local_after = after.astimezone(zone)
    spread = datetime.timedelta(minutes=spread_minutes)

    def at(day: datetime.date) -> datetime.datetime:
        return (datetime.datetime(day.year, day.month, day.day, h, m, tzinfo=zone) + spread).astimezone(datetime.timezone.utc)

    if cadence == "once":
        assert run_on is not None
        t = at(run_on)
        return t if t > after else None
    day = local_after.date()
    for _ in range(0, 400):  # at most a little over a year ahead
        ok = (cadence == "daily"
              or (cadence == "weekdays" and day.weekday() < 5)
              or (cadence == "weekly" and day.weekday() == weekday)
              or (cadence == "monthly" and day.day == month_day))
        if ok and at(day) > after:
            return at(day)
        day += datetime.timedelta(days=1)
    return None


def describe(cadence: str, at_time: str, tz: str, weekday: int | None, month_day: int | None, run_on: datetime.date | None) -> str:
    if cadence == "source":
        return "When a document changes in Knowledge"
    days = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]
    when = {"once": f"Once on {run_on.isoformat() if run_on else '?'}", "daily": "Every day", "weekdays": "Weekdays",
            "weekly": days[weekday] if weekday is not None else "Weekly", "monthly": f"Monthly on day {month_day}"}[cadence]
    return f"{when} at {at_time} ({tz})"
