"""What the model is offered from an installed integration, and what it is not (decision 0008)."""

import yaml
from pathlib import Path

from nortpole.work.integrations.chat_tools import MAX_RESULT_CHARS, parameters_schema, tool_name
from nortpole.work.integrations.manifest import Integration

ROOT = Path(__file__).resolve().parents[6] / "integrations"


def load(path: str) -> Integration:
    return Integration.model_validate(yaml.safe_load((ROOT / path / "integration.yaml").read_text(encoding="utf-8")))


WIKI = load("horizontal/product/wikipedia")
AIR = load("horizontal/automations/airtable")


def action(integration: Integration, action_id: str):  # type: ignore[no-untyped-def]
    return next(a for a in integration.actions if a.id == action_id)


def test_the_model_is_offered_only_the_parameters_meant_for_it() -> None:
    search = parameters_schema(action(WIKI, "search"))
    assert set(search["properties"]) == {"query"}, "limit is the person's setting (fill user) and is never offered"
    assert search["required"] == ["query"] and search["additionalProperties"] is False
    lists = parameters_schema(action(AIR, "list_records"))
    assert {"baseId", "tableId", "maxRecords", "filterFormula", "pageSize", "offset", "view"} == set(lists["properties"])
    assert lists["required"] == ["baseId", "tableId"]
    assert lists["properties"]["pageSize"] == {"description": "Records per page (1 to 100).", "type": "integer", "minimum": 1, "maximum": 100}


def test_object_parameters_and_enums_are_described_to_the_model() -> None:
    create = parameters_schema(action(AIR, "create_record"))
    assert create["properties"]["fields"]["type"] == "object" and create["properties"]["fields"]["additionalProperties"] is True
    spotify = load("horizontal/product/spotify")
    top = parameters_schema(action(spotify, "get_my_top_items"))["properties"]["type"]
    assert top["enum"] == ["artists", "tracks"]


def test_tool_names_are_valid_function_names_and_distinct_across_the_catalog() -> None:
    import glob

    seen: set[str] = set()
    for f in glob.glob(str(ROOT / "horizontal/*/*/integration.yaml")):
        integration = Integration.model_validate(yaml.safe_load(open(f, encoding="utf-8")))
        for a in integration.actions:
            name = tool_name(integration, a)
            assert name.replace("_", "").isalnum() and len(name) <= 64, name
            assert name not in seen, f"{name} is used twice"
            seen.add(name)


def test_the_result_limit_is_a_sane_size() -> None:
    assert 5_000 <= MAX_RESULT_CHARS <= 100_000


def test_a_tool_binds_to_the_agent_runtime_with_a_valid_definition() -> None:
    import uuid

    from nortpole.tools.models import ToolContext
    from nortpole.work.integrations.chat_tools import IntegrationChatTool

    tool = IntegrationChatTool(uuid.uuid4(), AIR, action(AIR, "list_records"))
    assert tool.id is None and tool.name == "airtable_list_records"
    bound = tool.bind(lambda: ToolContext())
    assert bound.definition.name == "airtable_list_records"
    assert bound.definition.parameters["type"] == "object" and bound.definition.parameters["required"] == ["baseId", "tableId"]
    assert "never changes anything" in tool.description
