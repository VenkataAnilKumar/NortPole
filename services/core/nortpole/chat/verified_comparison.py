"""Derive comparisons from explicitly stated facts in authorized passages."""

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_COMPARISON = re.compile(
    r"\b(?:compar(?:ed?|ison|ing)|contrast|same|differ\w*|changed?|unchanged|versus|vs)\b",
    re.I,
)
_FIELD = re.compile(r"(?P<label>[A-Za-z][\w /-]{1,50}):\s+(?P<value>[^:]{1,160})")
_BOLD_FIELD = re.compile(
    r"(?P<marker>\*\*|__)(?P<label>[A-Za-z][\w /-]{1,50})"
    r"(?::(?P=marker)|(?P=marker):)\s+(?P<value>[^:]{1,160})"
)
_LIST_MARKER = re.compile(r"^(?:[-+*]|[0-9]+[.)])\s+")
_TIMED_APPROVAL = re.compile(
    r"(?P<owner>[A-Z][A-Za-z &-]{0,59}) approves "
    r"(?P<scope>standard [a-z][a-z -]{1,50}) "
    r"(?P<window>(?:in|within) [0-9]{1,4} (?:(?:business|calendar) )?days?)\."
)
_ACTIVATION_REVIEW = re.compile(
    r"(?P<owner>[A-Z][A-Za-z &-]{0,59}?) (?:still )?reviews "
    r"(?P<scope>high-risk [a-z][a-z -]{1,50}) before activation\."
)


@dataclass(frozen=True)
class Comparison:
    label: str
    values: dict[str, str]
    agrees: bool


def is_comparison_question(question: str) -> bool:
    return _COMPARISON.search(question) is not None


def compare_passages(question: str, documents: Mapping[str, Sequence[str]]) -> list[Comparison]:
    if len(documents) < 2 or not is_comparison_question(question):
        return []

    by_field: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    labels: dict[str, str] = {}
    statements: dict[str, dict[str, str]] = defaultdict(dict)
    for document, lines in documents.items():
        for raw_line in lines:
            line = " ".join(raw_line.split())
            field_line = _LIST_MARKER.sub("", line, count=1)
            if match := _TIMED_APPROVAL.fullmatch(line):
                scope = match["scope"]
                fields = (
                    (f"Approver for {scope}", match["owner"]),
                    (f"Approval window for {scope}", match["window"]),
                )
            elif match := _ACTIVATION_REVIEW.fullmatch(line):
                fields = ((f"Reviewer before activation for {match['scope']}", match["owner"]),)
            elif match := _FIELD.fullmatch(field_line) or _BOLD_FIELD.fullmatch(field_line):
                fields = ((match["label"], match["value"]),)
            else:
                fields = ()
            for label, value in fields:
                key = label.casefold()
                labels.setdefault(key, label)
                by_field[key][document].add(value)

            # Only cite statements that are repeated verbatim across documents.
            if not fields and 4 <= len(line.split()) <= 30 and line.endswith("."):
                statements[line].setdefault(document, line)

    comparisons = []
    for key, candidates in by_field.items():
        # Missing or conflicting values cannot establish a single comparison.
        if candidates.keys() != documents.keys() or any(
            len(values) != 1 for values in candidates.values()
        ):
            continue
        values = {document: next(iter(candidates[document])) for document in documents}
        comparisons.append(Comparison(labels[key], values, agrees=len(set(values.values())) == 1))
        if len(comparisons) == 6:
            return comparisons
    for line, values in statements.items():
        if values.keys() == documents.keys():
            comparisons.append(Comparison("Repeated statement", values, agrees=True))
        if len(comparisons) == 6:
            break
    return comparisons
