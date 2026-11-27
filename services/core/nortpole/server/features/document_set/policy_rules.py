from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, StrictBool
from sqlalchemy.orm import Session

from nortpole.auth.permissions import require_permission
from nortpole.chat.policy_rules import (
    MAX_RULES,
    PolicyConfiguration,
    PolicyRule,
    PolicyRuleInput,
    current_fingerprint,
    supports_rule,
)
from nortpole.chat.search_evidence import resolve_library_passage
from nortpole.context.search.models import PersonaSearchInfo
from nortpole.db.document_set import get_document_set_by_id, get_document_set_by_id_for_user
from nortpole.db.engine.sql_engine import get_session
from nortpole.db.enums import Permission
from nortpole.db.models import DocumentSet, User
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ContextFileMetadata
from nortpole.server.query_and_chat.models import SearchEvidenceReference
from nortpole.server.utils_vector_db import require_vector_db

router = APIRouter(
    prefix="/admin/document-set/{document_set_id}/policy-rules",
    dependencies=[Depends(require_vector_db)],
)
Editor = Annotated[User, Depends(require_permission(Permission.MANAGE_DOCUMENT_SETS, allow_scope=True))]
Database = Annotated[Session, Depends(get_session)]


class RuleView(BaseModel):
    id: UUID
    source_title: str
    rule: PolicyRuleInput | None


class RuleList(BaseModel):
    enabled: bool
    rules: list[RuleView]


class PolicyMode(BaseModel):
    enabled: StrictBool


def _library(db: Session, user: User, library_id: int, *, write: bool = False) -> DocumentSet:
    if write and get_document_set_by_id(db, library_id, for_update=True) is None:
        raise NortPoleError(NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND)
    library = get_document_set_by_id_for_user(db, library_id, user, get_editable=True)
    if library is None:
        raise NortPoleError(NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND)
    return library


def _passage(library: DocumentSet, source: SearchEvidenceReference, user: User) -> ContextFileMetadata | None:
    return resolve_library_passage(
        source, library.id, PersonaSearchInfo(
            document_set_names=[library.name], search_start_date=None,
            attached_document_ids=[], hierarchy_node_ids=[],
        ), user,
    )


def _view(rule: PolicyRule, passage: ContextFileMetadata) -> RuleView:
    return RuleView(
        id=rule.id,
        source_title=passage.filename,
        rule=(
            PolicyRuleInput.model_validate(rule.model_dump(exclude={"id", "fingerprint"}))
            if current_fingerprint(passage) == rule.fingerprint else None
        ),
    )


@router.get("")
def list_rules(document_set_id: int, user: Editor, db: Database) -> RuleList:
    library = _library(db, user, document_set_id)
    configuration = PolicyConfiguration.model_validate(library.policy_configuration or {})
    return RuleList(enabled=configuration.enabled, rules=[
        _view(rule, passage)
        for rule in configuration.rules
        if (passage := _passage(library, rule.source, user)) is not None
    ])


@router.patch("")
def set_mode(document_set_id: int, mode: PolicyMode, user: Editor, db: Database) -> PolicyMode:
    library = _library(db, user, document_set_id, write=True)
    configuration = PolicyConfiguration.model_validate(library.policy_configuration or {})
    configuration.enabled = mode.enabled
    library.policy_configuration = configuration.model_dump(mode="json")
    db.commit()
    return mode


def _find(
    library: DocumentSet, configuration: PolicyConfiguration, rule_id: UUID, user: User,
) -> int:
    for index, rule in enumerate(configuration.rules):
        if rule.id == rule_id and _passage(library, rule.source, user) is not None:
            return index
    raise NortPoleError(NortPoleErrorCode.DOCUMENT_SET_NOT_FOUND, "Policy rule is unavailable.")


def _save_rule(
    library: DocumentSet, payload: PolicyRuleInput, user: User, db: Session, rule_id: UUID | None = None,
) -> RuleView:
    configuration = PolicyConfiguration.model_validate(library.policy_configuration or {})
    index = _find(library, configuration, rule_id, user) if rule_id is not None else len(configuration.rules)
    if index >= MAX_RULES:
        raise NortPoleError(NortPoleErrorCode.CONFLICT, "This library has reached its policy rule limit.")
    passage = _passage(library, payload.source, user)
    if passage is None or not supports_rule(payload, passage):
        raise NortPoleError(
            NortPoleErrorCode.INVALID_INPUT,
            "Select an available passage and quote the exact text containing the answer, its unit, and any threshold comparison.",
        )
    rule = PolicyRule(**payload.model_dump(), id=rule_id or uuid4(), fingerprint=current_fingerprint(passage))
    if rule_id is None:
        configuration.rules.append(rule)
    else:
        configuration.rules[index] = rule
    library.policy_configuration = configuration.model_dump(mode="json")
    result = _view(rule, passage)
    db.commit()
    return result


@router.post("", status_code=201)
def add_rule(document_set_id: int, payload: PolicyRuleInput, user: Editor, db: Database) -> RuleView:
    library = _library(db, user, document_set_id, write=True)
    return _save_rule(library, payload, user, db)


@router.put("/{rule_id}")
def edit_rule(document_set_id: int, rule_id: UUID, payload: PolicyRuleInput, user: Editor, db: Database) -> RuleView:
    library = _library(db, user, document_set_id, write=True)
    return _save_rule(library, payload, user, db, rule_id)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(document_set_id: int, rule_id: UUID, user: Editor, db: Database) -> Response:
    library = _library(db, user, document_set_id, write=True)
    configuration = PolicyConfiguration.model_validate(library.policy_configuration or {})
    del configuration.rules[_find(library, configuration, rule_id, user)]
    library.policy_configuration = configuration.model_dump(mode="json")
    db.commit()
    return Response(status_code=204)
