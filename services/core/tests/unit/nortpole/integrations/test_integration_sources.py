"""Integration definitions kept as source in the repository's integrations/ folder (decision 0008).

Every `integration.yaml` must be a definition the server accepts, sit in the folder its group and category name, and be
registered in `modules.json`; a definition adapted from Sim must name its source and the NOTICE must be present.
"""

import json
from pathlib import Path

import pytest
import yaml

from nortpole.work.integrations.manifest import Integration

REPO = Path(__file__).resolve().parents[6]
ROOT = REPO / "integrations"


def _sources() -> dict[Path, dict]:
    found = {}
    for path in sorted(ROOT.glob("*/*/*/integration.yaml")):
        found[path.parent] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return found


SOURCES = _sources()


def test_there_are_definitions() -> None:
    assert SOURCES


@pytest.mark.parametrize("folder", list(SOURCES), ids=lambda f: f.name)
def test_definition_is_accepted_by_the_server(folder: Path) -> None:
    Integration.model_validate(SOURCES[folder])


@pytest.mark.parametrize("folder", list(SOURCES), ids=lambda f: f.name)
def test_folder_matches_the_definition(folder: Path) -> None:
    definition = SOURCES[folder]
    group, category = folder.relative_to(ROOT).parts[:2]
    assert definition["id"] == folder.name, "the folder name must equal the integration id"
    assert definition["group"] == group, "the folder group must equal the definition's group"
    assert definition["category"] == category, "the folder category must equal the definition's category"


def test_ids_are_unique() -> None:
    ids = [d["id"] for d in SOURCES.values()]
    assert len(ids) == len(set(ids))


def test_every_definition_is_registered_and_every_registration_exists() -> None:
    inventory = json.loads((REPO / "modules.json").read_text(encoding="utf-8"))["integrations"]
    assert sorted(inventory["active"]) == sorted(folder.relative_to(REPO).as_posix() for folder in SOURCES)


def test_adapted_definitions_name_their_source_and_the_notice_is_present() -> None:
    adapted = [f for f in SOURCES if "Adapted from Sim" in (f / "integration.yaml").read_text(encoding="utf-8")
               or "adapted from Sim" in (f / "integration.yaml").read_text(encoding="utf-8")]
    assert adapted, "the first integrations are adapted from Sim"
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "Apache License" in notice and "simstudioai/sim" in notice
    assert (ROOT / "LICENSE-APACHE-2.0").is_file()
    for folder in adapted:
        text = (folder / "integration.yaml").read_text(encoding="utf-8")
        assert "Apache-2.0" in text and "tools/" in text, f"{folder.name} must name the Sim file it follows"


def test_no_definition_holds_a_secret_or_a_non_https_address() -> None:
    for folder in SOURCES:
        text = (folder / "integration.yaml").read_text(encoding="utf-8")
        assert "http://" not in text
        assert "Bearer " not in text.replace("Bearer {credential.access_token}", "")
