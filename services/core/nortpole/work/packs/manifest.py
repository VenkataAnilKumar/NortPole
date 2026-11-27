"""The pack manifest and its canonical form. Strict: unknown fields are errors,
sizes are capped, and ids are slugs, so a package cannot carry surprises."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, StrictInt, StrictStr, ConfigDict, Field, field_validator, model_validator

from nortpole.governance.route_policy.policy import DATA_CLASSES, ROUTE_KINDS

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewRule(_Strict):
    """A check on a draft, before it can be approved. Declarative only: a rule names one of
    the built-in kinds, so no pack runs code. A "block" rule that fails stops approval; a
    "warn" rule is shown to the reviewer and does not."""

    kind: Literal["min_citations", "max_words", "must_include", "must_not_include", "all_claims_supported"]
    value: StrictInt | StrictStr | None = None
    severity: Literal["block", "warn"] = "block"
    message: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _value_matches_kind(self) -> "ReviewRule":
        if self.kind in ("min_citations", "max_words"):
            lo, hi = (1, 20) if self.kind == "min_citations" else (10, 5000)
            if not isinstance(self.value, int) or isinstance(self.value, bool) or not lo <= self.value <= hi:
                raise ValueError(f"{self.kind} needs a whole number from {lo} to {hi}")
        elif self.kind in ("must_include", "must_not_include"):
            if not isinstance(self.value, str) or not 1 <= len(self.value.strip()) <= 100:
                raise ValueError(f"{self.kind} needs a phrase of 1 to 100 characters")
        elif self.value is not None:
            raise ValueError(f"{self.kind} takes no value")
        return self


GUIDE_BODY_MAX = 4000
GUIDES_PER_TEMPLATE_MAX = 3
GUIDE_TEXT_PER_TEMPLATE_MAX = 6000


class Guide(_Strict):
    """Written know-how a template can use: how to do this kind of work. Text only: a guide cannot run anything,
    add a source, widen access or change a rule. It is shown in full when the pack is reviewed."""

    id: str
    name: str = Field(min_length=1, max_length=80)
    # What it is for and when to use it; shown to people and to the planner.
    description: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=GUIDE_BODY_MAX)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("guide id must be a lower-case slug")
        return v


# The tools a workflow agent may name. Code runs them; the model only proposes steps that use them.
WORKFLOW_TOOLS = {"search": "Search the libraries the person can open"}
MAX_SEARCHES_LIMIT = 4


class AgentSpec(_Strict):
    """A workflow agent: a planner with instructions that proposes tool steps, which the person accepts and code runs.
    It acts as the person asking, can only propose sends, and never calls anything itself."""

    id: str
    name: str = Field(min_length=1, max_length=80)
    # The agent card: what it does, in plain words.
    description: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=2000)
    guides: list[str] = Field(default_factory=list, max_length=GUIDES_PER_TEMPLATE_MAX)
    tools: list[str] = Field(min_length=1, max_length=len(WORKFLOW_TOOLS))
    max_searches: int = Field(default=3, ge=1, le=MAX_SEARCHES_LIMIT)
    chat_pilot: Literal["research", "reporting"] | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("agent id must be a lower-case slug")
        return v

    @field_validator("tools")
    @classmethod
    def _tools(cls, v: list[str]) -> list[str]:
        bad = [t for t in v if t not in WORKFLOW_TOOLS]
        if bad:
            raise ValueError(f"unknown workflow tool: {bad[0]} (known: {', '.join(WORKFLOW_TOOLS)})")
        if len(set(v)) != len(v):
            raise ValueError("a tool is listed twice")
        return v


class Template(_Strict):
    id: str
    title: str = Field(min_length=1, max_length=200)
    request: str = Field(min_length=1, max_length=4000)
    desired_output: str = Field(default="", max_length=2000)
    # House style for the draft: wording and layout only. It is added to the
    # prompt below the citation rules and cannot change them.
    style: str = Field(default="", max_length=800)
    review_rules: list[ReviewRule] = Field(default_factory=list, max_length=10)
    # Ids of this pack's guides that drafts from this template use; only these are loaded.
    guides: list[str] = Field(default_factory=list, max_length=GUIDES_PER_TEMPLATE_MAX)
    # The id of this pack's agent that runs drafts from this template, if any.
    agent: str | None = None

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
    """One check a model must pass before the pack runs on it. The case carries
    its own evidence passages, so it runs the same on any route. With no
    evidence the case expects the "no source covers this" notice. `expect` must
    appear in the draft (case-insensitive); with evidence, the draft must also
    cite at least one of the passages."""

    question: str = Field(min_length=1, max_length=500)
    expect: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=3)
    # Run the case with this template's house style, so a style that makes the
    # model drop its citations is caught before the pack is offered.
    template: str | None = None

    @field_validator("evidence")
    @classmethod
    def _ev(cls, v: list[str]) -> list[str]:
        if any(not p.strip() or len(p) > 1500 for p in v):
            raise ValueError("evidence passages must be 1 to 1500 characters")
        return v


class Manifest(_Strict):
    schema_version: Literal[1]
    # The validators below enforce these patterns; json_schema_extra publishes them in the generated schema too.
    id: str = Field(json_schema_extra={"pattern": SLUG.pattern})
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(json_schema_extra={"pattern": SEMVER.pattern})
    vertical: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=2000)
    templates: list[Template] = Field(min_length=1, max_length=25)
    requires: Requirements
    requests: Requests = Requests()
    # The most this pack's tasks may do with a result. "draft_only": a send can be
    # prepared and reviewed but not approved or sent. It can only lower what a
    # destination allows, never raise it.
    autonomy: Literal["draft_only", "act_with_approval"] = "act_with_approval"
    # Checks every draft from this pack must pass (in addition to each template's own).
    review_rules: list[ReviewRule] = Field(default_factory=list, max_length=10)
    evaluation_cases: list[EvalCase] = Field(default_factory=list, max_length=100)
    guides: list[Guide] = Field(default_factory=list, max_length=20)
    agents: list[AgentSpec] = Field(default_factory=list, max_length=10)

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

    @model_validator(mode="after")
    def _case_templates_exist(self) -> "Manifest":
        ids = {t.id for t in self.templates}
        bad = [c.template for c in self.evaluation_cases if c.template and c.template not in ids]
        if bad:
            raise ValueError(f"evaluation case names a template that does not exist: {bad[0]}")
        return self

    @model_validator(mode="after")
    def _guides_exist_and_fit(self) -> "Manifest":
        by_id = {g.id: g for g in self.guides}
        if len(by_id) != len(self.guides):
            raise ValueError("guide ids must be unique")
        for t in self.templates:
            missing = [g for g in t.guides if g not in by_id]
            if missing:
                raise ValueError(f"template {t.id} names a guide that does not exist: {missing[0]}")
            if len(set(t.guides)) != len(t.guides):
                raise ValueError(f"template {t.id} names the same guide twice")
            if sum(len(by_id[g].body) for g in t.guides) > GUIDE_TEXT_PER_TEMPLATE_MAX:
                raise ValueError(f"template {t.id}: its guides are longer than {GUIDE_TEXT_PER_TEMPLATE_MAX} characters together")
        return self

    @model_validator(mode="after")
    def _agents_exist_and_fit(self) -> "Manifest":
        agents = {a.id: a for a in self.agents}
        if len(agents) != len(self.agents):
            raise ValueError("agent ids must be unique")
        guides = {g.id for g in self.guides}
        for a in self.agents:
            missing = [g for g in a.guides if g not in guides]
            if missing:
                raise ValueError(f"agent {a.id} names a guide that does not exist: {missing[0]}")
        for t in self.templates:
            if t.agent is not None and t.agent not in agents:
                raise ValueError(f"template {t.id} names an agent that does not exist: {t.agent}")
        return self

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
