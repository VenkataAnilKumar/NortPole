"""Which administrator changes need a second administrator. Off by default: with one administrator the rule would
lock them out of their own settings. Turning a rule ON takes effect at once; changing the rules while any is on needs
a second administrator too, otherwise one administrator could switch the protection off alone."""

from __future__ import annotations

from pydantic import BaseModel

from evolvxsi.key_value_store.factory import get_kv_store
from evolvxsi.key_value_store.interface import KvKeyNotFoundError

KV_KEY = "evolvxsi_admin_controls"
KINDS = ("route_policy", "retention", "controls")


class AdminControls(BaseModel):
    version: int = 1
    second_for_route_policy: bool = False  # model routes, data classes, redaction
    second_for_retention: bool = False  # retention periods and the legal hold


def load() -> AdminControls:
    try:
        return AdminControls.model_validate(get_kv_store().load(KV_KEY))
    except (KvKeyNotFoundError, ValueError):
        return AdminControls()
    except Exception:  # noqa: BLE001 - an unreadable store must not make changes silently easier or harder: defaults apply
        return AdminControls()


def save(c: AdminControls) -> None:
    get_kv_store().store(KV_KEY, c.model_dump())


def required(kind: str) -> bool:
    c = load()
    if kind == "route_policy":
        return c.second_for_route_policy
    if kind == "retention":
        return c.second_for_retention
    if kind == "controls":
        return c.second_for_route_policy or c.second_for_retention
    return False
