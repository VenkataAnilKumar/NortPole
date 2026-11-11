"""Access rules for knowledge sources, checked against the fixed A5 test set."""

import json
from pathlib import Path

import pytest

from evolvxsi.access.models import DocumentAccess
from evolvxsi.knowledge_access.decisions import (
    CitationState,
    SourceDocument,
    Viewer,
    check_citations,
    filter_evidence,
    may_see,
    must_withhold,
    viewer_acl,
)

TEST_SET = json.loads((Path(__file__).parent / "a5_test_set.json").read_text())


def _viewer(name: str) -> Viewer:
    v = TEST_SET["viewers"][name]
    return Viewer(
        email=v["email"],
        groups=frozenset(v.get("groups", [])),
        is_admin=v.get("is_admin", False),
    )


def _documents() -> dict[str, SourceDocument]:
    docs = {}
    for d in TEST_SET["documents"]:
        a = d["access"]
        access = (
            None
            if a is None
            else DocumentAccess.build(
                user_emails=a.get("user_emails", []),
                user_groups=a.get("user_groups", []),
                external_user_emails=a.get("external_user_emails", []),
                external_user_group_ids=a.get("external_user_group_ids", []),
                is_public=a.get("is_public", False),
            )
        )
        docs[d["doc_id"]] = SourceDocument(
            doc_id=d["doc_id"],
            title=d["title"],
            access=access,
            superseded_by=d.get("superseded_by"),
        )
    return docs


DOCS = _documents()
QUESTIONS = {q["id"]: q for q in TEST_SET["questions"]}


@pytest.mark.parametrize("question_id", sorted(QUESTIONS))
@pytest.mark.parametrize("viewer_name", sorted(TEST_SET["viewers"]))
def test_only_listed_viewers_can_open_every_cited_document(
    question_id: str, viewer_name: str
) -> None:
    question = QUESTIONS[question_id]
    if not question["must_cite"]:
        pytest.skip("nothing to cite")
    viewer = _viewer(viewer_name)
    can_open_all = all(may_see(viewer, DOCS[d]) for d in question["must_cite"])
    assert can_open_all == (viewer_name in question["answerable_by"])


def test_anonymous_viewer_gets_public_documents_only() -> None:
    assert viewer_acl(_viewer("anonymous")) == {"PUBLIC"}
    view = filter_evidence(_viewer("anonymous"), list(DOCS.values()))
    assert [d.doc_id for d in view.visible] == ["handbook-public"]


def test_group_membership_grants_access() -> None:
    assert may_see(_viewer("analyst"), DOCS["policy-travel-v2"])
    assert not may_see(_viewer("contractor"), DOCS["policy-travel-v2"])


def test_unknown_access_fails_closed_except_for_admin() -> None:
    doc = DOCS["unsynced-contract"]
    assert not may_see(_viewer("analyst"), doc)
    assert not may_see(_viewer("anonymous"), doc)
    assert may_see(_viewer("admin"), doc)


def test_admin_role_does_not_open_documents_with_a_known_access_list() -> None:
    # Administrative permission governs configuration, not content.
    assert not may_see(_viewer("admin"), DOCS["board-acquisition-memo"])


def test_hidden_documents_are_counted_but_not_described() -> None:
    view = filter_evidence(_viewer("contractor"), list(DOCS.values()))
    assert [d.doc_id for d in view.visible] == ["handbook-public"]
    assert view.hidden_count == len(DOCS) - 1
    assert not hasattr(view, "hidden")


def test_restricted_citation_reveals_no_title() -> None:
    (check,) = check_citations(_viewer("analyst"), ["board-acquisition-memo"], DOCS)
    assert check.state is CitationState.ACCESS_REMOVED
    assert check.title is None
    assert must_withhold([check])


def test_superseded_citation_is_flagged_not_withheld() -> None:
    (check,) = check_citations(_viewer("analyst"), ["policy-travel-v1"], DOCS)
    assert check.state is CitationState.SUPERSEDED
    assert check.superseded_by == "policy-travel-v2"
    assert not must_withhold([check])


def test_revocation_withholds_an_answer_that_was_available() -> None:
    analyst = _viewer("analyst")
    cited = ["policy-travel-v2", "handbook-public"]
    assert not must_withhold(check_citations(analyst, cited, DOCS))

    removed = Viewer(email=analyst.email, groups=frozenset())
    checks = check_citations(removed, cited, DOCS)
    assert [c.state for c in checks] == [
        CitationState.ACCESS_REMOVED,
        CitationState.AVAILABLE,
    ]
    assert must_withhold(checks)


def test_missing_document_withholds() -> None:
    checks = check_citations(_viewer("analyst"), ["deleted-doc"], DOCS)
    assert checks[0].state is CitationState.MISSING
    assert must_withhold(checks)


def test_prior_email_still_matches_until_resync() -> None:
    doc = SourceDocument(
        doc_id="d",
        title="t",
        access=DocumentAccess.build(["old@example.com"], [], [], [], False),
    )
    renamed = Viewer(
        email="new@example.com", prior_emails=frozenset({"old@example.com"})
    )
    assert may_see(renamed, doc)
