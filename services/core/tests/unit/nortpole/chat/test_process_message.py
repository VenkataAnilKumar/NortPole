from unittest.mock import Mock
from uuid import uuid4

import pytest

from nortpole.chat import process_message
from nortpole.chat.process_message import remove_answer_citations
from nortpole.db.enums import LLMModelFlowType
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.policy import RoutePolicy
from nortpole.llm.override_models import LLMOverride
from nortpole.server.query_and_chat.models import SendMessageRequest


def test_remove_answer_citations_strips_http_markdown_citation() -> None:
    answer = "The answer is Paris [[1]](https://example.com/doc)."

    assert remove_answer_citations(answer) == "The answer is Paris."


def test_remove_answer_citations_strips_empty_markdown_citation() -> None:
    answer = "The answer is Paris [[1]]()."

    assert remove_answer_citations(answer) == "The answer is Paris."


def test_remove_answer_citations_strips_citation_with_parentheses_in_url() -> None:
    answer = (
        "The answer is Paris "
        "[[1]](https://en.wikipedia.org/wiki/Function_(mathematics))."
    )

    assert remove_answer_citations(answer) == "The answer is Paris."


def test_remove_answer_citations_preserves_non_citation_markdown_links() -> None:
    answer = (
        "See [reference](https://example.com/Function_(mathematics)) "
        "for context [[1]](https://en.wikipedia.org/wiki/Function_(mathematics))."
    )

    assert (
        remove_answer_citations(answer)
        == "See [reference](https://example.com/Function_(mathematics)) for context."
    )


def test_chat_model_selection_persists_manual_choice_and_clears_on_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = Mock(name="provider")
    provider.name = "Workspace AI"
    provider.provider = "openai"
    model = Mock(
        id=42,
        is_visible=True,
        is_router=False,
        llm_model_flow_types=[LLMModelFlowType.CHAT],
        llm_provider=provider,
        llm_provider_id=1,
        custom_display_name="Workspace model",
    )
    model.name = "workspace-model"
    session = Mock(persona=Mock(id=0), current_alternate_model=None)
    settings = Mock(
        model_routing_enabled=False, model_routing_model_configuration_id=42
    )
    for name, result in (
        ("fetch_user_group_ids", set()),
        ("has_global_permission", False),
        ("can_user_access_llm_provider", True),
        ("fetch_model_configuration_by_id", model),
        ("fetch_default_model", model),
        ("load_settings", settings),
        ("load_policy", RoutePolicy(route_kinds={"1": "local"})),
    ):
        monkeypatch.setattr(process_message, name, Mock(return_value=result))

    manual = SendMessageRequest(
        message="hello",
        chat_session_id=uuid4(),
        model_selection="manual",
        llm_override=LLMOverride(model_configuration_id=42),
    )
    auto = SendMessageRequest(
        message="hello", chat_session_id=uuid4(), model_selection="auto"
    )
    result = process_message._chat_model_override(manual, session, Mock(), Mock())
    assert result.model_configuration_id == 42
    assert session.current_alternate_model == "Workspace AI__openai__workspace-model__mc:42"
    result = process_message._chat_model_override(auto, session, Mock(), Mock())
    assert result.model_configuration_id == 42
    assert session.current_alternate_model is None

    settings.model_routing_enabled = True
    model.is_router = True
    result = process_message._chat_model_override(auto, session, Mock(), Mock())
    assert result.model_configuration_id == 42
    process_message.fetch_default_model.assert_called_once()

    model.is_visible = False
    with pytest.raises(NortPoleError, match="No chat model is available"):
        process_message._chat_model_override(manual, session, Mock(), Mock())


@pytest.mark.parametrize("allowed_kinds,expected", [(["local", "private"], 3), (["private"], 2), ([], 1)])
def test_chat_auto_uses_accessible_allowed_fallback(
    monkeypatch: pytest.MonkeyPatch, allowed_kinds: list[str], expected: int
) -> None:
    def candidate(model_id: int, provider_id: int, *, router: bool = False) -> Mock:
        return Mock(
            id=model_id,
            is_visible=True,
            is_router=router,
            llm_model_flow_types=[LLMModelFlowType.CHAT],
            llm_provider=Mock(id=provider_id),
            llm_provider_id=provider_id,
            custom_display_name=f"Model {model_id}",
        )

    default = candidate(1, 1)
    private = candidate(2, 2)
    local = candidate(3, 3)
    inaccessible = candidate(4, 4)
    router = candidate(5, 1, router=True)
    policy = RoutePolicy(
        allowed={"confidential": allowed_kinds},
        route_kinds={"1": "cloud", "2": "private", "3": "local", "4": "local"},
    )
    for name, result in (
        ("fetch_user_group_ids", set()),
        ("has_global_permission", False),
        ("fetch_default_model", default),
        ("fetch_model_configuration_by_id", router),
        ("fetch_existing_models", [inaccessible, private, local, default]),
        ("load_policy", policy),
        ("load_settings", Mock(model_routing_enabled=True, model_routing_model_configuration_id=5)),
    ):
        monkeypatch.setattr(process_message, name, Mock(return_value=result))
    monkeypatch.setattr(
        process_message, "can_user_access_llm_provider",
        lambda provider, *_: provider.id != 4,
    )
    request = SendMessageRequest(
        message="hello", chat_session_id=uuid4(), model_selection="auto"
    )
    session = Mock(persona=Mock(id=0), current_alternate_model=None)
    result = process_message._chat_model_override(request, session, Mock(), Mock())
    assert result.model_configuration_id == expected


def test_chat_model_selection_rejects_override_of_agent_model() -> None:
    request = SendMessageRequest(
        message="hello",
        chat_session_id=uuid4(),
        model_selection="manual",
        llm_override=LLMOverride(model_configuration_id=42),
    )
    session = Mock(persona=Mock(id=10, default_model_configuration_id=7))
    with pytest.raises(NortPoleError, match="Select a model available for this agent"):
        process_message._chat_model_override(request, session, Mock(), Mock())


def test_selected_skills_add_only_authorized_enabled_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_id = uuid4()
    skill = Mock()
    lookup = Mock(return_value=skill)
    status = Mock(enabled=True, is_valid=True, is_available=True, external_app=None)
    preview = Mock()
    preview.name = "Receipt review"
    preview.instructions_markdown = "Check that the date and amount are present."
    monkeypatch.setattr(process_message, "fetch_skill", lookup)
    monkeypatch.setattr(process_message, "skill_response_for_user", Mock(return_value=status))
    monkeypatch.setattr(process_message, "skill_preview_response", Mock(return_value=preview))
    user, session = Mock(), Mock()

    context = process_message._selected_skill_context([skill_id, skill_id], user, session)
    assert context == "Selected skill: Receipt review\nCheck that the date and amount are present."
    lookup.assert_called_once_with(
        skill_id,
        policy=process_message.SkillManagementPolicy.VIEW,
        user=user,
        db_session=session,
    )

    status.enabled = False
    with pytest.raises(NortPoleError, match="unavailable in chat"):
        process_message._selected_skill_context([skill_id], user, session)

    lookup.return_value = None
    with pytest.raises(NortPoleError, match="Skill is unavailable"):
        process_message._selected_skill_context([skill_id], user, session)
