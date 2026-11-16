"""The integration definitions this deployment offers, read from the repository's `integrations/` folder.

`NORTPOLE_INTEGRATIONS_DIR` points somewhere else (a packaged copy). A definition that does not validate is skipped and
logged, so one bad file never hides the rest. With no folder the registry is empty and nothing is offered."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from nortpole.utils.logger import setup_logger
from nortpole.work.integrations.manifest import Integration

logger = setup_logger()


def definitions_dir() -> Path:
    configured = os.environ.get("NORTPOLE_INTEGRATIONS_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[5] / "integrations"


@lru_cache(maxsize=1)
def _load(folder: str) -> dict[str, Integration]:
    found: dict[str, Integration] = {}
    for path in sorted(Path(folder).glob("*/*/*/integration.yaml")):
        try:
            item = Integration.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 - one bad file must not hide the others
            logger.warning("skipped an integration definition that does not validate: %s", path, exc_info=True)
            continue
        group, category = path.relative_to(folder).parts[:2]
        if item.id in found or (item.group, item.category) != (group, category) or item.id != path.parent.name:
            logger.warning("skipped an integration definition in the wrong place or with a repeated id: %s", path)
            continue
        found[item.id] = item
    return found


def all_integrations() -> dict[str, Integration]:
    return dict(_load(str(definitions_dir())))


def get(integration_id: str) -> Integration | None:
    return _load(str(definitions_dir())).get(integration_id)


def reload() -> None:
    _load.cache_clear()
