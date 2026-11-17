"""Who may use an integration: the administrator's policy, one answer per item.

Three answers: **allowed** (people install and connect it themselves), **needs_approval** (a person asks and an
administrator approves, once, for that person) and **blocked** (nobody). The answer comes from, in order: an override on
the integration, an override on its category, then the definition's own default. A "blocked" anywhere above the
default wins. A write action can never start as "allowed" because the definition format refuses it; an administrator
may still choose to allow it on purpose, and that choice is audited."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nortpole.key_value_store.factory import get_kv_store
from nortpole.key_value_store.interface import KvKeyNotFoundError
from nortpole.work.integrations.manifest import CATEGORIES, SLUG, Integration

from nortpole.utils.logger import setup_logger

logger = setup_logger()

KV_KEY = "nortpole_integration_policy"
Answer = Literal["allowed", "needs_approval", "blocked"]


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # id -> answer
    integrations: dict[str, Answer] = Field(default_factory=dict, max_length=2000)
    # "horizontal/automations" -> answer
    categories: dict[str, Answer] = Field(default_factory=dict, max_length=100)

    @field_validator("integrations")
    @classmethod
    def _ids(cls, value: dict[str, Answer]) -> dict[str, Answer]:
        bad = [k for k in value if not SLUG.match(k)]
        if bad:
            raise ValueError(f"not integration ids: {bad}")
        return value

    @field_validator("categories")
    @classmethod
    def _categories(cls, value: dict[str, Answer]) -> dict[str, Answer]:
        for key in value:
            group, _, category = key.partition("/")
            if group not in CATEGORIES or category not in CATEGORIES[group]:
                raise ValueError(f"{key!r} is not a group/category")
        return value


def load() -> PolicyConfig:
    try:
        return PolicyConfig.model_validate(get_kv_store().load(KV_KEY))
    except KvKeyNotFoundError:
        return PolicyConfig()
    except Exception:  # noqa: BLE001 - a damaged setting must not open anything up
        logger.exception("The integration policy could not be read; blocking every integration until it can be")
        return PolicyConfig(categories={f"{g}/{c}": "blocked" for g, cs in CATEGORIES.items() for c in cs})


def save(config: PolicyConfig) -> None:
    get_kv_store().store(KV_KEY, config.model_dump())


def resolve(integration: Integration, config: PolicyConfig | None = None) -> Answer:
    config = config if config is not None else load()
    own = config.integrations.get(integration.id)
    by_category = config.categories.get(f"{integration.group}/{integration.category}")
    if own == "blocked" or by_category == "blocked":
        return "blocked"
    return own or by_category or integration.policy_default
