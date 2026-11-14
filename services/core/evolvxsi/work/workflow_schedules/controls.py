"""Who may schedule workflows. Off by default: an administrator turns scheduling on, for everyone or for chosen
groups. Turning it off pauses every schedule at its next run."""

from __future__ import annotations

from pydantic import BaseModel, Field

from evolvxsi.key_value_store.factory import get_kv_store
from evolvxsi.key_value_store.interface import KvKeyNotFoundError

KV_KEY = "evolvxsi_schedule_controls"


class ScheduleControls(BaseModel):
    version: int = 1
    enabled: bool = False
    groups: list[str] = Field(default_factory=list)  # group names; empty means everyone, once enabled
    max_per_person: int = Field(default=10, ge=1, le=50)


def load() -> ScheduleControls:
    try:
        return ScheduleControls.model_validate(get_kv_store().load(KV_KEY))
    except (KvKeyNotFoundError, ValueError):
        return ScheduleControls()
    except Exception:  # noqa: BLE001 - an unreadable store fails closed: scheduling stays off
        return ScheduleControls()


def save(c: ScheduleControls) -> None:
    get_kv_store().store(KV_KEY, c.model_dump())


def allowed_for(c: ScheduleControls, group_names: set[str]) -> bool:
    return c.enabled and (not c.groups or bool(set(c.groups) & group_names))
