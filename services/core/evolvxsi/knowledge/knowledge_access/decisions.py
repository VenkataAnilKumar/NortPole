"""Who may see which source document, and what happens to citations.

The access-control strings use the same format as `DocumentAccess.to_acl`, so
a decision made here matches what an index filter would return.

Rules (see the A5 design document):

* A viewer sees a document when at least one of the viewer's access strings
  is on the document's access list.
* Unknown access fails closed: a document with no access list is visible to
  administrators only.
* A hidden document is counted but never described: no title, no passage.
* An answer is withheld when any passage it cites is no longer visible to the
  person opening it.
"""

from dataclasses import dataclass, field
from enum import Enum

from evolvxsi.access.models import DocumentAccess
from evolvxsi.access.utils import (
    prefix_external_group,
    prefix_user_email,
    prefix_user_group,
)
from evolvxsi.configs.constants import PUBLIC_DOC_PAT


@dataclass(frozen=True)
class Viewer:
    """The person asking, as far as access is concerned."""

    email: str | None
    groups: frozenset[str] = frozenset()
    external_groups: frozenset[str] = frozenset()
    prior_emails: frozenset[str] = frozenset()
    is_admin: bool = False

    @property
    def is_anonymous(self) -> bool:
        return self.email is None


@dataclass(frozen=True)
class SourceDocument:
    """One version of one document from a connected source."""

    doc_id: str
    title: str
    # None means the access list is not known (never synced, or sync failed
    # before any list was stored).
    access: DocumentAccess | None
    # Set when a newer version replaces this one.
    superseded_by: str | None = None


class CitationState(str, Enum):
    AVAILABLE = "available"
    SUPERSEDED = "superseded"
    ACCESS_REMOVED = "access_removed"
    MISSING = "missing"


@dataclass(frozen=True)
class CitationCheck:
    doc_id: str
    state: CitationState
    # Only filled in when the viewer may see the document.
    title: str | None = None
    superseded_by: str | None = None


@dataclass(frozen=True)
class EvidenceView:
    visible: list[SourceDocument] = field(default_factory=list)
    # How many documents matched but are hidden from this viewer. Titles and
    # ids of hidden documents are deliberately not carried.
    hidden_count: int = 0


def viewer_acl(viewer: Viewer) -> set[str]:
    """Access strings for a viewer. Anonymous viewers get public documents only."""
    if viewer.is_anonymous:
        return {PUBLIC_DOC_PAT}
    acl = {PUBLIC_DOC_PAT, prefix_user_email(viewer.email)}  # type: ignore[arg-type]
    acl.update(prefix_user_email(e) for e in viewer.prior_emails)
    acl.update(prefix_user_group(g) for g in viewer.groups)
    acl.update(prefix_external_group(g) for g in viewer.external_groups)
    return acl


def may_see(viewer: Viewer, document: SourceDocument) -> bool:
    if document.access is None:
        return viewer.is_admin and not viewer.is_anonymous
    return bool(viewer_acl(viewer) & document.access.to_acl())


def filter_evidence(viewer: Viewer, documents: list[SourceDocument]) -> EvidenceView:
    visible = [d for d in documents if may_see(viewer, d)]
    return EvidenceView(visible=visible, hidden_count=len(documents) - len(visible))


def check_citations(
    viewer: Viewer,
    cited_doc_ids: list[str],
    documents: dict[str, SourceDocument],
) -> list[CitationCheck]:
    """Re-check every citation for the person opening an answer.

    A document the viewer may not see is reported as `access_removed` whether or
    not it exists, so the result does not reveal that a restricted document is
    there. `missing` is used only when nothing with that id exists and the
    distinction therefore reveals nothing.
    """
    checks: list[CitationCheck] = []
    for doc_id in cited_doc_ids:
        document = documents.get(doc_id)
        if document is None:
            checks.append(CitationCheck(doc_id=doc_id, state=CitationState.MISSING))
        elif not may_see(viewer, document):
            checks.append(
                CitationCheck(doc_id=doc_id, state=CitationState.ACCESS_REMOVED)
            )
        elif document.superseded_by is not None:
            checks.append(
                CitationCheck(
                    doc_id=doc_id,
                    state=CitationState.SUPERSEDED,
                    title=document.title,
                    superseded_by=document.superseded_by,
                )
            )
        else:
            checks.append(
                CitationCheck(
                    doc_id=doc_id, state=CitationState.AVAILABLE, title=document.title
                )
            )
    return checks


def must_withhold(checks: list[CitationCheck]) -> bool:
    """An answer is withheld when any cited passage cannot be opened by the
    viewer. Superseded sources do not withhold; they are flagged instead."""
    return any(
        c.state in (CitationState.ACCESS_REMOVED, CitationState.MISSING)
        for c in checks
    )
