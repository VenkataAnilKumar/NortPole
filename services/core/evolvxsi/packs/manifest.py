"""The pack manifest and its canonical form. Strict: unknown fields are errors,
sizes are capped, and ids are slugs, so a package cannot carry surprises."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from evolvxsi.route_policy.policy import DATA_CLASSES, ROUTE_KINDS

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Template(_Strict):
    id: str
    title: str = Field(min_length=1, max_length=200)
    request: str = Field(min_length=1, max_length=4000)
    desired_output: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("template id must be a lower-case slug")
        return v


class Requirements(_Strict):
    """Where the pack may run. The workspace's data class must be listed, and
    the model route in use must be one of the listed kinds."""

    data_classes: list[str] = Field(min_length=1)
    route_kinds: list[str] = Field(min_length=1)

    @field_validator("data_classes")
    @classmethod
    def _dc(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in DATA_CLASSES]
        if bad:
            raise ValueError(f"unknown data class: {', '.join(bad)}")
        return sorted(set(v))

    @field_validator("route_kinds")
    @classmethod
    def _rk(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in ROUTE_KINDS]
        if bad:
            raise ValueError(f"unknown route kind: {', '.join(bad)}")
        return sorted(set(v))


class Requests(_Strict):
    """Permissions the pack would like. Listing one grants nothing: an
    administrator's own settings decide, and today none of these is honoured
    automatically."""

    send_destinations: bool = False
    personal_connectors: bool = False


class EvalCase(_Strict):
    question: str = Field(min_length=1, max_length=500)
    expect: str = Field(min_length=1, max_length=500)


class Manifest(_Strict):
    schema_version: Literal[1]
    id: str
    name: str = Field(min_length=1, max_length=120)
    version: str
    vertical: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=2000)
    templates: list[Template] = Field(min_length=1, max_length=25)
    requires: Requirements
    requests: Requests = Requests()
    evaluation_cases: list[EvalCase] = Field(default_factory=list, max_length=100)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("pack id must be a lower-case slug")
        return v

    @field_validator("version")
    @classmethod
    def _version(cls, v: str) -> str:
        if not SEMVER.match(v):
            raise ValueError("version must look like 1.2.3")
        return v

    @field_validator("templates")
    @classmethod
    def _unique(cls, v: list[Template]) -> list[Template]:
        ids = [t.id for t in v]
        if len(ids) != len(set(ids)):
            raise ValueError("template ids must be unique")
        return v


def canonical_bytes(manifest: dict) -> bytes:
    """The exact bytes that are signed and hashed: sorted keys, no whitespace."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(manifest: dict) -> str:
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def version_key(v: str) -> tuple[int, int, int]:
    a, b, c = (int(x) for x in v.split("."))
    return a, b, c
