from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError

ROUTE_KINDS: tuple[str, ...] = ("local", "private", "cloud")
DATA_CLASSES: tuple[str, ...] = ("public", "internal", "confidential", "restricted")
# Preference order when the user picks "Auto": most contained route first.
AUTO_PREFERENCE: tuple[str, ...] = ("local", "private", "cloud")
KV_KEY = "evolvxsi_route_policy"
UNASSIGNED_KIND = "cloud"  # a provider with no kind is treated as the least contained


def default_allowed() -> dict[str, list[str]]:
    return {
        "public": ["local", "private", "cloud"],
        "internal": ["local", "private"],
        "confidential": ["local", "private"],
        "restricted": ["local"],
    }


class RoutePolicy(BaseModel):
    version: int = 1
    default_data_class: str = "confidential"
    allowed: dict[str, list[str]] = Field(default_factory=default_allowed)
    # provider id (as a string) -> route kind
    route_kinds: dict[str, str] = Field(default_factory=dict)
    # Route kinds whose requests have listed sensitive patterns replaced before sending.
    redact_route_kinds: list[str] = Field(default_factory=lambda: ["cloud"])

    @field_validator("redact_route_kinds")
    @classmethod
    def _check_redact(cls, v: list[str]) -> list[str]:
        for k in v:
            if k not in ROUTE_KINDS:
                raise ValueError(f"unknown route kind: {k}")
        return list(dict.fromkeys(v))

    @field_validator("default_data_class")
    @classmethod
    def _check_default_class(cls, v: str) -> str:
        if v not in DATA_CLASSES:
            raise ValueError(f"unknown data class: {v}")
        return v

    @field_validator("allowed")
    @classmethod
    def _check_allowed(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for data_class in DATA_CLASSES:
            kinds = v.get(data_class, [])
            for k in kinds:
                if k not in ROUTE_KINDS:
                    raise ValueError(f"unknown route kind: {k}")
            out[data_class] = list(dict.fromkeys(kinds))
        extra = set(v) - set(DATA_CLASSES)
        if extra:
            raise ValueError(f"unknown data class: {sorted(extra)[0]}")
        return out

    @field_validator("route_kinds")
    @classmethod
    def _check_kinds(cls, v: dict[str, str]) -> dict[str, str]:
        for pid, kind in v.items():
            if kind not in ROUTE_KINDS:
                raise ValueError(f"unknown route kind for provider {pid}: {kind}")
        return v


class RouteDecision(BaseModel):
    allowed: bool
    kind: str
    data_class: str
    reason: str | None = None


def kind_for(policy: RoutePolicy, provider_id: int) -> str:
    return policy.route_kinds.get(str(provider_id), UNASSIGNED_KIND)


def decide(policy: RoutePolicy, provider_id: int, data_class: str | None = None) -> RouteDecision:
    """Pure decision: may this provider's route process this data class?"""
    cls = data_class or policy.default_data_class
    if cls not in DATA_CLASSES:
        cls = policy.default_data_class
    kind = kind_for(policy, provider_id)
    unassigned = str(provider_id) not in policy.route_kinds
    if kind in policy.allowed.get(cls, []):
        return RouteDecision(allowed=True, kind=kind, data_class=cls)
    note = " (route type not set, treated as cloud)" if unassigned else ""
    return RouteDecision(
        allowed=False,
        kind=kind,
        data_class=cls,
        reason=f"Policy v{policy.version} does not allow {cls} data on {kind} routes{note}.",
    )


def load_policy() -> RoutePolicy:
    try:
        raw = get_kv_store().load(KV_KEY)
    except KvKeyNotFoundError:
        return RoutePolicy()
    try:
        return RoutePolicy.model_validate(raw)
    except Exception:
        # A damaged policy must not silently open routes: fall back to the defaults.
        return RoutePolicy()


def save_policy(policy: RoutePolicy) -> RoutePolicy:
    get_kv_store().store(KV_KEY, policy.model_dump())
    return policy
