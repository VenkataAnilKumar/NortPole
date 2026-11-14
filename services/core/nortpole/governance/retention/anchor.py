"""The hash of the last audit row a prune removed, so the chain from the first kept row still verifies."""

from __future__ import annotations

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError

KV_KEY = "evolvxsi_audit_anchor"


def load_anchor() -> str | None:
    try:
        v = get_kv_store().load(KV_KEY)
        return v.get("hash") if isinstance(v, dict) else None
    except KvKeyNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        return None


def save_anchor(h: str) -> None:
    get_kv_store().store(KV_KEY, {"hash": h})
