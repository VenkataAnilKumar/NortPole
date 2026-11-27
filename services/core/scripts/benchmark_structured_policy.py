"""Check whether authored policy rules support claims with explicit conditions."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Literal

Scalar = str | int


@dataclass(frozen=True)
class Condition:
    field: str
    value: Scalar
    operator: Literal["equals", "greater_than"] = "equals"

    def accepts(self, value: Scalar) -> bool:
        if self.operator == "greater_than":
            return type(value) is int and type(self.value) is int and value > self.value
        return type(value) is type(self.value) and value == self.value


@dataclass(frozen=True)
class Answer:
    value: Scalar
    unit: str | None = None


@dataclass(frozen=True)
class Rule:
    source_id: str
    fingerprint: str
    excerpt: str
    action: str
    conditions: tuple[Condition, ...]
    answer_field: str
    answer: Answer


@dataclass(frozen=True)
class Claim:
    action: str
    conditions: Mapping[str, Scalar]
    answer_field: str
    answer: Answer


def fingerprint(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def verify(
    claim: Claim, rules: Sequence[Rule], authorized_sources: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    matches = []
    for rule in rules:
        if rule.action != claim.action or rule.answer_field != claim.answer_field:
            continue
        if {condition.field for condition in rule.conditions} != claim.conditions.keys():
            continue
        if not all(condition.accepts(claim.conditions[condition.field]) for condition in rule.conditions):
            continue
        text = authorized_sources.get(rule.source_id)
        if text is None:
            continue
        if not rule.excerpt or rule.excerpt not in text or fingerprint(text) != rule.fingerprint:
            return ()
        matches.append(rule)
    # A conflict among current authorized sources leaves the claim unverified.
    if not matches or any(
        type(rule.answer.value) is not type(claim.answer.value) or rule.answer != claim.answer
        for rule in matches
    ):
        return ()
    return tuple(dict.fromkeys((rule.source_id, rule.excerpt) for rule in matches))


def authored_rule(
    source_id: str, text: str, action: str, conditions: tuple[Condition, ...],
    answer_field: str, answer: Answer,
) -> Rule:
    return Rule(source_id, fingerprint(text), text, action, conditions, answer_field, answer)


@dataclass(frozen=True)
class Pair:
    rule: Rule
    supported: Claim
    changed: Claim


def pair(
    source_id: str, text: str, action: str, conditions: Mapping[str, Scalar],
    answer_field: str, answer: Answer, /, **changed: object,
) -> Pair:
    rule = authored_rule(
        source_id, text, action, tuple(Condition(key, value) for key, value in conditions.items()),
        answer_field, answer,
    )
    supported = Claim(action, conditions, answer_field, answer)
    return Pair(rule, supported, replace(supported, **changed))


PAIRS = (
    pair("one-renewal", "The data owner can approve one renewal after contractor access expires.",
         "approve_renewal", {"grant": "contractor", "renewal": 1, "status": "expired"},
         "approver", Answer("data owner"),
         conditions={"grant": "contractor", "renewal": 2, "status": "expired"}),
    pair("unused-invite", "An unused reviewer invitation expires after 72 hours.",
         "expire_invitation", {"status": "unused"}, "duration", Answer(72, "hours"),
         action="end_project_access", conditions={"status": "accepted"}),
    pair("rush-fee", "The purchasing lead authorizes rush charges for revised delivery.",
         "authorize_rush_charge", {"delivery": "revised"}, "approver", Answer("purchasing lead"),
         action="authorize_refund", conditions={"delivery": "completed"}),
    pair("support-sla", "Support acknowledges each billing dispute within one business day.",
         "acknowledge", {"case": "billing dispute"}, "deadline", Answer(1, "business_day"), action="resolve"),
    pair("deletion-unit", "Delete primary data within 30 calendar days of contract termination.",
         "delete", {"data": "primary", "trigger": "contract termination"}, "deadline", Answer(30, "calendar_day"),
         answer=Answer(30, "business_day")),
    pair("legal-hold", "Purge archived records after five years if they are free of legal hold.",
         "purge", {"record": "archived", "legal_hold": "absent"}, "retention", Answer(5, "years"),
         conditions={"record": "archived", "legal_hold": "active"}),
    pair("paused-schedule", "A manually started run leaves the next timer slot unchanged.",
         "start_run", {"trigger": "manual"}, "next_timer_slot", Answer("unchanged"),
         action="pause_schedule", conditions={"run": "manual_in_progress"},
         answer_field="manual_run", answer=Answer("cancelled")),
)


def main() -> None:
    checked = 0

    def check(label: str, claim: Claim, rules: Sequence[Rule], sources: Mapping[str, str], expected: bool) -> None:
        nonlocal checked
        evidence = verify(claim, rules, sources)
        if bool(evidence) != expected:
            raise AssertionError((label, expected, evidence))
        if any(source_id not in sources or excerpt not in sources[source_id] for source_id, excerpt in evidence):
            raise AssertionError((label, "Unverified excerpt"))
        print(label, "verified" if evidence else "abstained")
        checked += 1

    for fixture in PAIRS:
        rule = fixture.rule
        sources = {rule.source_id: rule.excerpt}
        check(rule.source_id + "/supported", fixture.supported, (rule,), sources, True)
        check(rule.source_id + "/changed-condition", fixture.changed, (rule,), sources, False)

    renewal, _, _, _, deadline, legal, _ = PAIRS
    rule = renewal.rule
    sources = {rule.source_id: rule.excerpt}
    check("missing-renewal-number", replace(renewal.supported, conditions={"grant": "contractor", "status": "expired"}),
          (rule,), sources, False)
    check("extra-condition", replace(renewal.supported, conditions={**renewal.supported.conditions, "region": "Canada"}),
          (rule,), sources, False)
    check("revoked-source", renewal.supported, (rule,), {}, False)
    check("stale-source", renewal.supported, (rule,), {rule.source_id: rule.excerpt + " Approval policy suspended."}, False)
    check("detached-excerpt", renewal.supported, (replace(rule, excerpt="An unrelated statement."),), sources, False)

    conflict = authored_rule("conflicting-renewal", "Security approves the first renewal for an expired contractor grant.",
                             rule.action, rule.conditions, rule.answer_field, Answer("Security"))
    check("authorized-conflict", renewal.supported, (rule, conflict), {**sources, conflict.source_id: conflict.excerpt}, False)
    check("restricted-conflict", renewal.supported, (rule, conflict), sources, True)
    check("only-restricted-evidence", renewal.supported, (rule, conflict), {conflict.source_id: conflict.excerpt}, False)
    check("missing-time-unit", replace(deadline.supported, answer=Answer(30)), (deadline.rule,),
          {deadline.rule.source_id: deadline.rule.excerpt}, False)
    check("wrong-duration", replace(deadline.supported, answer=Answer(60, "calendar_day")), (deadline.rule,),
          {deadline.rule.source_id: deadline.rule.excerpt}, False)
    check("missing-hold-status", replace(legal.supported, conditions={"record": "archived"}), (legal.rule,),
          {legal.rule.source_id: legal.rule.excerpt}, False)

    dues = authored_rule("dues-approval", "A director must approve dues over 300 USD.", "approve_dues",
                         (Condition("amount", 300, "greater_than"), Condition("currency", "USD")),
                         "approver", Answer("director"))
    sources = {dues.source_id: dues.excerpt}
    claim = Claim(dues.action, {"amount": 450, "currency": "USD"}, dues.answer_field, dues.answer)
    check("above-threshold", claim, (dues,), sources, True)
    check("exact-boundary", replace(claim, conditions={"amount": 300, "currency": "USD"}), (dues,), sources, False)
    check("different-currency", replace(claim, conditions={"amount": 450, "currency": "CAD"}), (dues,), sources, False)
    print(f"{checked} structured policy checks passed.")


if __name__ == "__main__":
    main()
