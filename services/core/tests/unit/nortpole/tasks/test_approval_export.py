from nortpole.work.tasks.export import draft_fingerprint, to_markdown
from nortpole.work.tasks.states import TaskAction, TaskState, next_state

SRC = [{"n": 1, "doc_id": "a", "title": "Travel policy", "link": "https://x/a", "cited": True},
       {"n": 2, "doc_id": "b", "title": "Handbook", "link": None, "cited": False}]


def test_fingerprint_is_stable_and_changes_with_text_or_sources() -> None:
    base = draft_fingerprint("Receipts in 30 days [1].", SRC)
    assert base == draft_fingerprint("Receipts in 30 days [1].", SRC)
    assert base != draft_fingerprint("Receipts in 31 days [1].", SRC)
    assert base != draft_fingerprint("Receipts in 30 days [1].", SRC[:1])


def test_markdown_lists_only_cited_sources() -> None:
    md = to_markdown("Receipts", "Due in 30 days [1].", SRC)
    assert md.startswith("# Receipts")
    assert "1. [Travel policy](https://x/a)" in md and "Handbook" not in md


def test_markdown_without_sources_says_so() -> None:
    assert "_No sources were cited._" in to_markdown("T", "Gap.", [])


def test_approve_and_revise_from_a_ready_draft() -> None:
    assert next_state(TaskState.DRAFT_READY, TaskAction.APPROVE) is TaskState.APPROVED
    assert next_state(TaskState.DRAFT_READY, TaskAction.REVISE) is TaskState.DRAFT
