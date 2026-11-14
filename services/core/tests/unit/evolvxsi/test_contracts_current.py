"""packages/contracts holds files generated from the code; they must match what the code generates now."""

import importlib.util
import json
from collections import Counter
from pathlib import Path

CORE = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("generate_contracts", CORE / "scripts" / "generate_contracts.py")
assert _spec and _spec.loader
generate_contracts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_contracts)


def test_generated_contracts_are_current() -> None:
    stale = [
        path.relative_to(generate_contracts.REPO).as_posix()
        for path, text in generate_contracts.outputs().items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    assert not stale, f"Regenerate with `PYTHONPATH=. python scripts/generate_contracts.py`: {stale}"


def test_operation_ids_are_unique_so_clients_can_be_generated() -> None:
    spec = json.loads(generate_contracts.OPENAPI_PATH.read_text(encoding="utf-8"))
    ids = Counter(op["operationId"] for item in spec["paths"].values() for op in item.values())
    assert not [i for i, n in ids.items() if n > 1]
    assert len(spec["paths"]) > 50, "the description should cover EvolvXSI's routes"
