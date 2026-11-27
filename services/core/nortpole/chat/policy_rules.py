"""Answer authored Knowledge questions using current library evidence."""

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from nortpole.chat.models import PolicyAnswer
from nortpole.chat.search_evidence import (
    SearchEvidenceProvenance,
    resolve_library_passage,
)
from nortpole.chat.verified_excerpts import _plain
from nortpole.context.search.models import PersonaSearchInfo
from nortpole.db.models import DocumentSet, User
from nortpole.file_store.models import ContextFileMetadata
from nortpole.server.query_and_chat.models import SearchEvidenceReference

MAX_RULES = 50
ABSTENTION = "I couldn't verify an authored policy answer for this question in the available Knowledge passages."

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Excerpt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]

ThresholdComparison = Literal["gt", "gte", "lt", "lte"]
AMOUNT_SLOT = "{amount}"
_DECIMAL = r"[0-9]{1,12}(?:\.[0-9]{1,4})?"
_THRESHOLDS = {
    "gt": (r"strictly over|over|above|more than|greater than", "greater than"),
    "gte": (r"at least|no less than|greater than or equal to", "greater than or equal to"),
    "lt": (r"strictly under|under|below|less than|fewer than", "less than"),
    "lte": (r"at most|no more than|less than or equal to", "less than or equal to"),
}
_NEGATION = re.compile(r"\b(?:not|never|unless|except)\b|n['’]t\b", re.IGNORECASE)


def normalize_question(text: str) -> str:
    return " ".join(text.lower().split()).removesuffix("?").rstrip()


class PolicyRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionText] = Field(min_length=1, max_length=10)
    action: ShortText
    conditions: dict[ShortText, ShortText] = Field(default_factory=dict, max_length=12)
    answer_field: ShortText
    value: ShortText
    unit: ShortText | None = None
    threshold_comparison: ThresholdComparison | None = None
    excerpt: Excerpt
    source: SearchEvidenceReference

    @model_validator(mode="after")
    def validate_rule(self) -> "PolicyRuleInput":
        questions = {normalize_question(question) for question in self.questions}
        if "" in questions or len(questions) != len(self.questions):
            raise ValueError("Enter distinct, complete questions.")
        if self.threshold_comparison is None:
            if any(AMOUNT_SLOT in question for question in questions):
                raise ValueError("Choose a threshold comparison to use {amount}.")
            return self
        if re.fullmatch(rf"\$?{_DECIMAL}", self.value) is None:
            raise ValueError("Enter a decimal threshold without grouping separators.")
        if self.unit is None and not self.value.startswith("$"):
            raise ValueError("Enter the unit stated in the source passage.")
        for question in questions:
            if question.count(AMOUNT_SLOT) != 1:
                raise ValueError("Each threshold question needs exactly one {amount}.")
            before, after = question.split(AMOUNT_SLOT)
            if before[-1:].isdigit() or after[:1].isdigit():
                raise ValueError("Separate {amount} from other numbers.")
        return self


class PolicyRule(PolicyRuleInput):
    id: UUID
    fingerprint: str


class PolicyConfiguration(BaseModel):
    enabled: bool = False
    rules: list[PolicyRule] = Field(default_factory=list, max_length=MAX_RULES)


def render_policy_answer(answer: PolicyAnswer, citations: Mapping[str, int]) -> str:
    number = citations.get(answer.document_id) if answer.document_id else None
    if number is None:
        return ABSTENTION
    value = _plain(answer.value).replace("$", r"\$")
    excerpt = _plain(answer.excerpt).replace("$", r"\$")
    return f"**{value}**\n\n“{excerpt}” [[{number}]]"


def current_fingerprint(passage: ContextFileMetadata) -> str:
    return SearchEvidenceProvenance.capture([passage], None).sources[0].fingerprint


def _answer_value(rule: PolicyRuleInput) -> str:
    return " ".join(" ".join(part.split()) for part in (rule.value, rule.unit) if part)


def supports_rule(rule: PolicyRuleInput, passage: ContextFileMetadata) -> bool:
    excerpt = " ".join(rule.excerpt.split())
    content = " ".join(passage.file_content.split())
    value = _answer_value(rule)
    if excerpt not in content:
        return False
    # A numeric answer must match the whole quantity, including sign and decimals.
    left = r"(?<!\w)(?<!\d[.,])(?<![+\-−])" if value[0].isdigit() else r"(?<!\w)"
    right = r"(?!\w|[.,]\d)" if value[-1].isdigit() else r"(?!\w)"
    literal = f"{left}{re.escape(value)}{right}"
    if rule.threshold_comparison is None:
        return re.search(literal, excerpt, flags=re.IGNORECASE) is not None
    comparison = rule.threshold_comparison
    phrase, _ = _THRESHOLDS[comparison]
    pattern = rf"(?<!\w)(?:{phrase}) {literal}"
    if comparison == "gte":
        pattern += rf"|(?P<postfix>{literal} or more\b)"
    elif comparison == "lte":
        pattern += rf"|(?P<postfix>{literal} or less\b)"
    match = re.search(pattern, excerpt, flags=re.IGNORECASE)
    if match is None:
        return False
    # Inspect the original clause too so a cropped quote cannot hide negation.
    for occurrence in re.finditer(re.escape(excerpt), content):
        prefix = content[:occurrence.start() + match.start()]
        clause = re.split(r"[.!?;](?:\s|$)", prefix)[-1]
        if _NEGATION.search(clause) or re.search(r"\bno\s+$", clause, re.IGNORECASE):
            return False
        if match.groupdict().get("postfix") and any(
            re.search(rf"\b(?:{terms}|exactly)\s+$", clause, re.IGNORECASE)
            for terms, _ in _THRESHOLDS.values()
        ):
            return False
        suffix = content[occurrence.start() + match.end():]
        if re.match(r"\s+or\s+(?:equal\b|less\b|more\b|higher\b|lower\b|\$?\d)", suffix, re.IGNORECASE):
            return False
    return True


def _matched_amount(rule: PolicyRule, alias: str) -> Decimal | None:
    for question in rule.questions:
        before, after = normalize_question(question).split(AMOUNT_SLOT)
        match = re.fullmatch(rf"{re.escape(before)}({_DECIMAL}){re.escape(after)}", alias)
        if match:
            return Decimal(match[1])
    return None


def _threshold_answer(rule: PolicyRule, amount: Decimal, comparison: ThresholdComparison) -> str:
    limit = Decimal(rule.value.removeprefix("$"))
    meets = {
        "gt": amount > limit,
        "gte": amount >= limit,
        "lt": amount < limit,
        "lte": amount <= limit,
    }[comparison]
    outcome = "meets" if meets else "does not meet"
    label = _THRESHOLDS[comparison][1]
    return f"The amount {outcome} the stated threshold ({label} {_answer_value(rule)})."


def enabled_policy_libraries(db: Session, names: list[str]) -> list[tuple[int, PolicyConfiguration]]:
    libraries = db.execute(
        select(DocumentSet.id, DocumentSet.policy_configuration)
        .where(DocumentSet.name.in_(names), DocumentSet.policy_configuration.is_not(None))
        .order_by(DocumentSet.id)
    )
    return [
        (library_id, configuration)
        for library_id, raw in libraries
        if (configuration := PolicyConfiguration.model_validate(raw)).enabled
    ]


def resolve_policy_answer(
    question: str,
    libraries: list[tuple[int, PolicyConfiguration]],
    persona: PersonaSearchInfo,
    user: User,
    selection: Sequence[SearchEvidenceReference] | None,
) -> tuple[PolicyAnswer, ContextFileMetadata | None, int | None]:
    selected = (
        {(ref.document_id, ref.chunk_id) for ref in selection}
        if selection is not None else None
    )
    alias = normalize_question(question)
    matches: list[tuple[PolicyRule, ContextFileMetadata, int, str]] = []
    for library_id, configuration in libraries:
        for rule in configuration.rules:
            comparison = rule.threshold_comparison
            if comparison is None:
                if not any(normalize_question(item) == alias for item in rule.questions):
                    continue
                value = _answer_value(rule)
            else:
                amount = _matched_amount(rule, alias)
                if amount is None:
                    continue
                value = _threshold_answer(rule, amount, comparison)
            if selected is not None and (rule.source.document_id, rule.source.chunk_id) not in selected:
                continue
            passage = resolve_library_passage(rule.source, library_id, persona, user)
            if passage is None:
                continue
            if current_fingerprint(passage) != rule.fingerprint or not supports_rule(rule, passage):
                return PolicyAnswer(), None, None
            matches.append((rule, passage, library_id, value))

    if not matches:
        return PolicyAnswer(), None, None
    rule, passage, library_id, value = matches[0]
    expected = (rule.action, rule.conditions, rule.answer_field, rule.value, rule.unit, rule.threshold_comparison, value)
    if any(
        (candidate.action, candidate.conditions, candidate.answer_field, candidate.value,
         candidate.unit, candidate.threshold_comparison, answer) != expected
        for candidate, _, _, answer in matches[1:]
    ):
        return PolicyAnswer(), None, None
    return PolicyAnswer(document_id=rule.source.document_id, value=value, excerpt=rule.excerpt), passage, library_id
