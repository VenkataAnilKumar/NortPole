import json
from unittest.mock import Mock

import pytest

from nortpole.chat.meeting_recap import meeting_notes_prompt, render_meeting_recap, summarize_meeting
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError


_NOTES = """We agreed to ship on Tuesday.

Asha will send the draft by Friday.
Who owns the migration?"""


def test_recap_groups_verbatim_items_and_preserves_source_line_numbers() -> None:
    reply = json.dumps({"items": [
        {"kind": "question", "line": 4, "quote": "Who owns the migration?"},
        {"kind": "action", "line": 3, "quote": "Asha will send the draft by Friday.", "owner": "Asha", "due": "Friday"},
        {"kind": "decision", "line": 1, "quote": "We agreed to ship on Tuesday."},
    ]})
    recap = render_meeting_recap(_NOTES, reply)
    assert recap.index("### Decisions") < recap.index("### Action items") < recap.index("### Open questions")
    assert "“We agreed to ship on Tuesday.” (notes line 1)" in recap
    assert "(notes line 3) · Owner: Asha · Due: Friday" in recap
    assert "“Who owns the migration?” (notes line 4)" in recap


def test_recap_removes_unsupported_quotes_owners_and_due_dates() -> None:
    reply = json.dumps({"items": [
        {"kind": "action", "line": 3, "quote": "Asha will send the draft by Friday.", "owner": "Jordan", "due": "Tuesday"},
        {"kind": "decision", "line": 1, "quote": "We agreed to cancel the launch."},
        {"kind": "question", "line": 9, "quote": "Who owns the migration?"},
    ]})
    recap = render_meeting_recap(_NOTES, reply)
    assert "Owner: Not stated · Due: Not stated" in recap
    assert "could not be matched" in recap
    for unsupported in ("Jordan", "Tuesday", "cancel", "migration"):
        assert unsupported not in recap


def test_recap_fails_closed_when_reply_is_invalid() -> None:
    assert "could not be checked" in render_meeting_recap(_NOTES, "I have invented an action.")


def test_labelled_notes_keep_all_explicit_items_without_calling_the_model() -> None:
    notes = "\n".join([
        "Decision: Publish the guide.",
        "Action: Asha will check the draft by Friday.",
        "Action item: Review the rollout. Owner: Robin Due: 2026-11-27",
        "Open question: Who owns the migration?",
    ])
    llm = Mock()
    recap = summarize_meeting(llm, Mock(), notes, "unused")
    llm.invoke.assert_not_called()
    assert "Publish the guide." in recap
    assert "Owner: Asha · Due: Friday" in recap
    assert "Owner: Robin · Due: 2026-11-27" in recap
    assert "Who owns the migration?" in recap


def test_unlabelled_model_failure_preserves_explicit_decisions() -> None:
    recap = render_meeting_recap("Decision: Ship the guide.\nWe discussed scheduling.", "invalid JSON")
    assert "Ship the guide." in recap
    assert "could not verify the unlabelled notes" in recap


def test_model_line_selection_uses_the_original_note_for_the_quote() -> None:
    recap = render_meeting_recap("Ben will organize the survey by Monday.", '{"items":[{"kind":"action","line":1}]}')
    assert "“Ben will organize the survey by Monday.” (notes line 1) · Owner: Ben · Due: Monday" in recap


def test_notes_are_numbered_as_data_without_losing_blank_lines() -> None:
    prompt = json.loads(meeting_notes_prompt(_NOTES, lambda _: 25, 4096))
    assert list(prompt) == ["1", "3", "4"]


@pytest.mark.parametrize(("notes", "window", "expected"), [
    (" ", 4096, "Paste meeting notes"),
    ("a" * 16001, 4096, "16,000 characters"),
    ("a\n" * 251, 4096, "250 lines"),
    ("Some short notes", 100, "too long for the selected model"),
])
def test_notes_must_fit_limits(notes: str, window: int, expected: str) -> None:
    with pytest.raises(NortPoleError, match=expected) as error:
        meeting_notes_prompt(notes, lambda _: 25, window)
    assert error.value.error_code == NortPoleErrorCode.INVALID_INPUT
