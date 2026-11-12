"""Fingerprint a draft, and export an approved draft after a fresh access check.

Export re-checks, at the moment of export, that the person can still open every
source the draft cites, using the document access lists in the database (not
the copy stored in the index). If any cited source is no longer open to them,
or no longer exists, the export is withheld; the draft stays approved and can
be exported once access is restored or the task is redrafted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from evolvxsi.access.access import get_acl_for_user, get_access_for_documents
from evolvxsi.db.models import User


def draft_fingerprint(
    text: str, sources: list[dict[str, Any]] | None, claims: list[dict[str, Any]] | None = None
) -> str:
    body = json.dumps(
        {
            "text": text,
            "sources": [[s.get("n"), s.get("doc_id")] for s in (sources or [])],
            "decisions": [[c["i"], c.get("decision")] for c in (claims or [])],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AccessCheck:
    open_doc_ids: list[str]
    withheld: int  # cited sources the person can no longer open (titles not revealed)


def recheck_cited_sources(db_session: Session, user: User, sources: list[dict[str, Any]] | None) -> AccessCheck:
    cited = [s["doc_id"] for s in (sources or []) if s.get("cited")]
    if not cited:
        return AccessCheck(open_doc_ids=[], withheld=0)
    acl = get_acl_for_user(user, db_session)
    access = get_access_for_documents(cited, db_session)
    open_ids = [d for d in cited if acl & access[d].to_acl()]
    return AccessCheck(open_doc_ids=open_ids, withheld=len(cited) - len(open_ids))


def to_markdown(title: str, text: str, sources: list[dict[str, Any]] | None) -> str:
    lines = [f"# {title}", "", text.strip(), ""]
    cited = [s for s in (sources or []) if s.get("cited")]
    if cited:
        lines += ["## Sources", ""]
        for s in cited:
            label = f"[{s['title']}]({s['link']})" if s.get("link") else s["title"]
            lines.append(f"{s['n']}. {label}")
    else:
        lines.append("_No sources were cited._")
    return "\n".join(lines).rstrip() + "\n"
