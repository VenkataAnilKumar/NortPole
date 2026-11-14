"""First-party workflow packs kept as source in the repository's packs/ folder (decision 0006, phase 3).

Every `manifest.yaml` must be a manifest the server accepts, sit in the folder its `vertical` names, and be registered in
`modules.json`; every edition must name existing packs.
"""

import json
from pathlib import Path

import pytest
import yaml

from nortpole.work.packs.manifest import Manifest

REPO = Path(__file__).resolve().parents[6]
PACKS = REPO / "packs"


def _sources() -> dict[Path, dict]:
    found = {}
    for path in sorted(PACKS.glob("horizontal/*/manifest.yaml")) + sorted(PACKS.glob("vertical/*/*/manifest.yaml")):
        found[path.parent] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return found


SOURCES = _sources()


def test_there_are_horizontal_and_vertical_packs() -> None:
    kinds = {folder.relative_to(PACKS).parts[0] for folder in SOURCES}
    assert kinds == {"horizontal", "vertical"}


@pytest.mark.parametrize("folder", list(SOURCES), ids=lambda f: f.name)
def test_manifest_is_accepted_by_the_server(folder: Path) -> None:
    Manifest.model_validate(SOURCES[folder])


@pytest.mark.parametrize("folder", list(SOURCES), ids=lambda f: f.name)
def test_folder_matches_the_manifest(folder: Path) -> None:
    manifest = SOURCES[folder]
    parts = folder.relative_to(PACKS).parts
    assert manifest["id"] == folder.name, "the folder name must equal the pack id"
    if parts[0] == "horizontal":
        assert manifest["vertical"] == "general", "a horizontal pack is domain-neutral"
    else:
        assert manifest["vertical"] == parts[1], "a vertical pack sits in its industry's folder"


def test_pack_ids_are_unique() -> None:
    ids = [m["id"] for m in SOURCES.values()]
    assert len(ids) == len(set(ids))


def test_every_pack_is_registered_and_every_registration_exists() -> None:
    active = json.loads((REPO / "modules.json").read_text(encoding="utf-8"))["packs"]["active"]
    assert sorted(active) == sorted(folder.relative_to(REPO).as_posix() for folder in SOURCES)


def test_editions_name_existing_packs_and_include_their_industry() -> None:
    ids = {m["id"]: m for m in SOURCES.values()}
    editions = sorted((PACKS / "editions").glob("*.json"))
    assert editions, "at least one edition is expected"
    for path in editions:
        edition = json.loads(path.read_text(encoding="utf-8"))
        assert edition["edition"] == path.stem
        assert edition["packs"], f"{path.name} lists no packs"
        missing = [p for p in edition["packs"] if p not in ids]
        assert not missing, f"{path.name} names packs that do not exist: {missing}"
        verticals = {ids[p]["vertical"] for p in edition["packs"]}
        assert verticals <= {"general", path.stem}, f"{path.name} mixes in another industry's packs: {verticals}"


def test_the_template_is_a_valid_horizontal_manifest() -> None:
    template = yaml.safe_load((PACKS / "_template" / "manifest.yaml").read_text(encoding="utf-8"))
    Manifest.model_validate(template)
    assert template["vertical"] == "general"
