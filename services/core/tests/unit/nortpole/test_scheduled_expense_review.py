from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from nortpole.agents.models import RunStatus
from nortpole.db.enums import UserFileStatus
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.work.workflow_schedules import expense_review
from nortpole.work.workflow_schedules.models import ExpenseReviewInputs


@pytest.mark.parametrize("privacy", ["other_owner", "incognito"])
def test_scheduled_review_rejects_csv_outside_the_owners_history(monkeypatch, privacy):
    owner = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(expense_review, "has_global_permission", lambda *_: True)
    monkeypatch.setattr(expense_review, "get_document_set_by_id_for_user", Mock(return_value=SimpleNamespace(name="Policy")))
    file = SimpleNamespace(
        user_id=uuid4() if privacy == "other_owner" else owner.id,
        incognito=privacy == "incognito",
        name="expenses.csv",
    )
    monkeypatch.setattr(expense_review, "get_user_file_by_id", Mock(return_value=file))
    store = Mock()
    monkeypatch.setattr(expense_review, "get_default_file_store", store)
    with pytest.raises(NortPoleError, match="selected CSV is unavailable"):
        expense_review.resolve_inputs(Mock(), owner, ExpenseReviewInputs(library_id=1, csv_file_id=uuid4()))
    store.assert_not_called()


@pytest.mark.parametrize("needs_review", [False, True])
@pytest.mark.parametrize("link_run", [False, True])
def test_scheduled_review_reuses_chat_turn_and_its_citation_record(monkeypatch, needs_review, link_run):
    owner = SimpleNamespace(id=uuid4())
    file_id, chat_id = uuid4(), uuid4()
    monkeypatch.setattr(expense_review, "has_global_permission", lambda *_: True)
    monkeypatch.setattr(expense_review, "get_document_set_by_id_for_user", Mock(return_value=SimpleNamespace(name="Current Policy")))
    monkeypatch.setattr(expense_review, "get_user_file_by_id", Mock(return_value=SimpleNamespace(
        id=file_id, file_id="csv_storage_id", user_id=owner.id, incognito=False,
        name="expenses.csv", status=UserFileStatus.COMPLETED,
    )))
    monkeypatch.setattr(expense_review, "get_default_file_store", Mock(return_value=Mock(get_file_size=Mock(return_value=70))))
    monkeypatch.setattr(expense_review, "load_settings", Mock(return_value=SimpleNamespace(disable_default_assistant=False)))
    budget = Mock()
    monkeypatch.setattr(expense_review, "check_token_rate_limits", budget)
    run = SimpleNamespace(chat_session_id=None) if link_run else None
    reserve_chat = Mock(return_value=SimpleNamespace(id=chat_id))
    monkeypatch.setattr(expense_review, "create_chat_session", reserve_chat)
    def complete_chat(*_args, on_response_reserved=None):
        if on_response_reserved is not None:
            on_response_reserved(19)
        return SimpleNamespace(message_id=19, error_msg=None)

    chat = Mock(side_effect=complete_chat)
    monkeypatch.setattr(expense_review, "run_chat_turn", chat)
    db = Mock()
    db.get.return_value = SimpleNamespace(
        response_status=RunStatus.COMPLETE,
        receipt_review_needs_review=needs_review,
        chat_session_id=chat_id,
    )
    config = ExpenseReviewInputs(library_id=1, csv_file_id=file_id, policy_title="Travel Policy")
    outcome, actual_chat = expense_review.run_expense_review(db, owner, config, run=run)
    assert outcome == ("needs_review" if needs_review else "review_complete")
    assert actual_chat == chat_id
    budget.assert_called_once_with(owner)
    request, actor = chat.call_args.args
    assert actor is owner
    if run:
        assert run.chat_session_id == request.chat_session_id == chat_id
        assert run.chat_result_id == 19
        assert request.chat_session_info is None
        assert reserve_chat.call_args.kwargs["commit"] is False
    else:
        reserve_chat.assert_not_called()
    assert request.internal_search_filters.document_set == ["Current Policy"]
    assert request.receipt_review_policy_title == "Travel Policy"
    assert request.file_descriptors[0]["user_file_id"] == str(file_id)
