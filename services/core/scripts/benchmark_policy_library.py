"""Interpret contractor policy lookups for a scoped Knowledge library trial."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmark_structured_policy import Answer, Claim, Condition, Rule, Scalar, authored_rule, verify

APPROVER = r"who (?:can approve|approves|can sign off on|signs off on|can authorize|authorizes) (?:the |a )?"
ORDINAL = r"(?P<ordinal>first|second|one-time) renewal"
INCIDENT = r"(?: (?P<incident>during|without) a declared incident)?"
RENEWAL = re.compile(
    APPROVER + ORDINAL + r" (?:of|for) (?:an? |the )?(?P<state>expired|active) contractor (?:grant|access)" + INCIDENT
)
RENEWAL_AFTER_EXPIRY = re.compile(
    APPROVER + ORDINAL + r" (?:after|once) (?:a |the )?contractor (?:grant|access) (?:has expired|expires)" + INCIDENT
)
INVITATION = re.compile(
    r"how many (?P<unit>hours|calendar days|business days) (?:until|before) (?:an? |the )?"
    r"(?P<state>unused|accepted) contractor invitation expires"
)

POLICY_TEXT = {
    "renewal": "The data owner approves the first renewal of an expired contractor grant.",
    "incident": "Security Operations approves the second renewal of an expired contractor grant during a declared incident.",
    "invitation": "An unused contractor invitation expires after 72 hours.",
}

QUESTIONS = (
    ("Who can approve the first renewal of an expired contractor grant?", "renewal"),
    ("Who signs off on a one-time renewal once a contractor grant has expired?", "renewal"),
    ("Who authorizes the first renewal for expired contractor access?", "renewal"),
    ("Who can sign off on the second renewal of an expired contractor grant during a declared incident?", "incident"),
    ("Who approves the second renewal after a contractor grant expires during a declared incident?", "incident"),
    ("How many hours before an unused contractor invitation expires?", "invitation"),
    ("How many hours until the unused contractor invitation expires?", "invitation"),
    ("Who can approve a renewal of an expired contractor grant?", None),
    ("Who approves the first renewal of an active contractor grant?", None),
    ("Who can approve the first renewal of a contractor grant?", None),
    ("Who approves the second renewal of an expired contractor grant?", None),
    ("Who approves the second renewal of an expired contractor grant without a declared incident?", None),
    ("Who approves the second renewal of an expired contractor grant during a declared incident in Canada?", None),
    ("Who approves the first renewal of an expired employee grant?", None),
    ("How many calendar days before an unused contractor invitation expires?", None),
    ("How many hours before an accepted contractor invitation expires?", None),
)


@dataclass(frozen=True)
class PolicyQuestion:
    action: str
    conditions: Mapping[str, Scalar]
    answer_field: str
    unit: str | None = None


@dataclass(frozen=True)
class PolicyAnswer:
    answer: Answer
    evidence: tuple[tuple[str, str], ...]


def interpret(question: str) -> PolicyQuestion | None:
    text = " ".join(question.casefold().split()).removesuffix("?")
    match = RENEWAL.fullmatch(text) or RENEWAL_AFTER_EXPIRY.fullmatch(text)
    if match:
        conditions: dict[str, Scalar] = {
            "grant": "contractor",
            "renewal": 2 if match["ordinal"] == "second" else 1,
            "status": match.groupdict().get("state", "expired"),
        }
        if reason := match["incident"]:
            conditions["incident"] = "declared" if reason == "during" else "absent"
        return PolicyQuestion("approve_renewal", conditions, "approver")
    if match := INVITATION.fullmatch(text):
        return PolicyQuestion(
            "expire_invitation", {"invitee": "contractor", "status": match["state"]},
            "duration", match["unit"],
        )
    return None


def make_rules(ids: Mapping[str, str]) -> tuple[Rule, ...]:
    return (
        authored_rule(ids["renewal"], POLICY_TEXT["renewal"], "approve_renewal",
                     (Condition("grant", "contractor"), Condition("renewal", 1), Condition("status", "expired")),
                     "approver", Answer("data owner")),
        authored_rule(ids["incident"], POLICY_TEXT["incident"], "approve_renewal",
                     (Condition("grant", "contractor"), Condition("renewal", 2), Condition("status", "expired"),
                      Condition("incident", "declared")), "approver", Answer("Security Operations")),
        authored_rule(ids["invitation"], POLICY_TEXT["invitation"], "expire_invitation",
                     (Condition("invitee", "contractor"), Condition("status", "unused")),
                     "duration", Answer(72, "hours")),
    )


def lookup(question: str, rules: Sequence[Rule], sources: Mapping[str, str]) -> PolicyAnswer | None:
    request = interpret(question)
    if request is None:
        return None
    possible = {
        rule.answer for rule in rules if rule.source_id in sources and rule.action == request.action
        and rule.answer_field == request.answer_field and rule.answer.unit == request.unit
    }
    for answer in possible:
        claim = Claim(request.action, request.conditions, request.answer_field, answer)
        if evidence := verify(claim, rules, sources):
            return PolicyAnswer(answer, evidence)
    return None


def check_questions(ids: Mapping[str, str], sources: Mapping[str, str]) -> tuple[int, int]:
    rules = make_rules(ids)
    verified = 0
    for question, key in QUESTIONS:
        expected = ids[key] if key is not None and ids[key] in sources else None
        answer = lookup(question, rules, sources)
        actual = [source_id for source_id, _ in answer.evidence] if answer else []
        if actual != ([expected] if expected is not None else []):
            raise AssertionError((question, expected, actual))
        verified += int(bool(actual))
    return verified, len(QUESTIONS) - verified


if __name__ == "__main__":
    demo_ids = {key: key for key in POLICY_TEXT}
    for allowed in (set(POLICY_TEXT), {"renewal", "invitation"}):
        print(check_questions(demo_ids, {key: POLICY_TEXT[key] for key in allowed}))
