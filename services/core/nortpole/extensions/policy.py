from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError

KV_KEY = "nortpole_extensions"
_HOST = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


class ExtensionPolicy(BaseModel):
    version: int = 1
    # "self_serve": people may add personal skills (today's behaviour). "off": they may not.
    # A "request" level (people ask, an administrator approves) is not built.
    personal_skills: Literal["off", "self_serve"] = "self_serve"
    # When on, an MCP server may be added and called only if its host is listed. Off by default.
    mcp_allowlist_enabled: bool = False
    mcp_allowed_hosts: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("mcp_allowed_hosts")
    @classmethod
    def _hosts(cls, v: list[str]) -> list[str]:
        out = []
        for h in v:
            h = h.strip().lower()
            if not _HOST.match(h):
                raise ValueError(f"not a host name: {h[:60]!r} (use example.com or *.example.com)")
            out.append(h)
        return list(dict.fromkeys(out))


def load() -> ExtensionPolicy:
    try:
        return ExtensionPolicy.model_validate(get_kv_store().load(KV_KEY))
    except (KvKeyNotFoundError, ValueError):
        return ExtensionPolicy()
    except Exception:  # noqa: BLE001
        # An unreadable store must not widen access: with the allowlist unknown, treat it as on and empty.
        return ExtensionPolicy(mcp_allowlist_enabled=True, mcp_allowed_hosts=[])


def save(p: ExtensionPolicy) -> None:
    get_kv_store().store(KV_KEY, p.model_dump())


def host_of(url: str | None) -> str | None:
    try:
        return (urlparse(url or "").hostname or "").lower() or None
    except ValueError:
        return None


def host_allowed(url: str | None, policy: ExtensionPolicy | None = None) -> bool:
    """With the allowlist off everything is allowed. With it on, the host must match a listed
    host exactly, or a `*.example.com` entry (any subdomain, not example.com itself)."""
    p = policy or load()
    if not p.mcp_allowlist_enabled:
        return True
    host = host_of(url)
    if not host:
        return False
    for allowed in p.mcp_allowed_hosts:
        if allowed == host or (allowed.startswith("*.") and host.endswith(allowed[1:])):
            return True
    return False
