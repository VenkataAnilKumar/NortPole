"""Retention settings. The periods below are PLACEHOLDERS: they have not been agreed
with any customer or checked against any legal requirement. A legal hold stops all
pruning until it is lifted."""

from __future__ import annotations

from pydantic import BaseModel, Field

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError

KV_KEY = "evolvxsi_retention"
MIN_DAYS, MAX_DAYS = 30, 3650  # a floor, so a typo cannot wipe the log


class Retention(BaseModel):
    version: int = 1
    audit_days: int | None = Field(default=365, ge=MIN_DAYS, le=MAX_DAYS)       # None keeps events forever
    usage_days: int | None = Field(default=365, ge=MIN_DAYS, le=MAX_DAYS)       # route usage and redaction counters
    legal_hold: bool = False
    hold_reason: str = Field(default="", max_length=500)
    hold_set_by: str | None = None
    last_prune_at: str | None = None
    last_prune_summary: str | None = None


def load() -> Retention:
    try:
        return Retention.model_validate(get_kv_store().load(KV_KEY))
    except (KvKeyNotFoundError, ValueError):
        return Retention()
    except Exception:  # noqa: BLE001 - an unreadable store must not delete anything: defaults still prune only past a year
        return Retention()


def save(r: Retention) -> None:
    get_kv_store().store(KV_KEY, r.model_dump())
