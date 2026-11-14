from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class QuietHours(BaseModel):
    enabled: bool = False
    start: str = "22:00"
    end: str = "07:00"

    @field_validator("start", "end")
    @classmethod
    def _valid_time(cls, v: str) -> str:
        if not _TIME.match(v):
            raise ValueError("time must be HH:MM")
        return v


class NotificationPreferences(BaseModel):
    # Items that need the user to act. On by default; nothing is lost by default.
    approvals: bool = True
    # Finished, failed and scheduled-run updates.
    run_updates: bool = True
    quiet_hours: QuietHours = Field(default_factory=QuietHours)


class UserPreferences(BaseModel):
    default_route: Literal["auto", "local", "private", "cloud"] = "auto"
    notifications: NotificationPreferences = Field(default_factory=NotificationPreferences)


def _key(user_id: str) -> str:
    return f"evolvxsi_user_prefs:{user_id}"


def load_preferences(user_id: str) -> UserPreferences:
    try:
        raw = get_kv_store().load(_key(user_id))
    except KvKeyNotFoundError:
        return UserPreferences()
    try:
        return UserPreferences.model_validate(raw)
    except Exception:
        # A damaged record falls back to the defaults rather than failing the page.
        return UserPreferences()


def save_preferences(user_id: str, prefs: UserPreferences) -> UserPreferences:
    get_kv_store().store(_key(user_id), prefs.model_dump())
    return prefs
