"""Compare rows from the Markdown tables present in two authorized passages."""

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

_SEPARATOR = re.compile(r":?-{3,}:?")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CURRENCY = r"(?:USD|CAD|EUR|GBP|AUD|JPY|CHF|INR|CNY|NZD|[$€£¥]|CA\$|US\$)"
_AMOUNT = re.compile(
    rf"(?:(?P<currency>{_CURRENCY})\s*)?"
    r"(?P<number>[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)"
    r"(?:\s*(?P<unit>%|[A-Za-z]+(?: [A-Za-z]+){0,2}))?",
    re.IGNORECASE,
)
_DURATION = re.compile(r"(?:(?:business|calendar) )?(?:hours?|days?|minutes?|weeks?|months?|years?)")


@dataclass(frozen=True)
class TableFinding:
    label: str
    first: str | None
    second: str | None
    status: str


def _cells(line: str) -> tuple[str, ...]:
    text = line.strip()
    # Both outer pipes must be present so a clipped passage cannot turn a
    # partially retrieved cell into a verified value.
    if (
        not text.startswith("|")
        or not text.endswith("|")
        or text.endswith(r"\|")
        or r"\\" in text
        or line.startswith(("    ", "\t"))
    ):
        return ()
    parts = re.split(r"(?<!\\)\|", text[1:-1])
    return tuple(" ".join(part.replace(r"\|", "|").split()) for part in parts)


def _visible_lines(passage: str) -> list[str]:
    lines = []
    fence = ""
    for line in passage.splitlines():
        match = _FENCE.match(line)
        if match:
            if not fence:
                fence = match[1]
            elif match[1].startswith(fence) and not line[match.end():].strip():
                fence = ""
            lines.append("")
        else:
            lines.append("" if fence else line)
    return lines


def _table_cells(passages: Sequence[str]) -> dict[tuple[str, str, str], list[tuple[str, str]]]:
    cells: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for passage in passages:
        lines = _visible_lines(passage)
        index = 0
        while index + 1 < len(lines):
            headers = _cells(lines[index])
            separators = _cells(lines[index + 1])
            fields = tuple(header.casefold() for header in headers)
            index += 1
            if (
                len(headers) < 2
                or len(headers) != len(separators)
                or len(set(fields)) != len(fields)
                or not all(fields)
                or not all(_SEPARATOR.fullmatch(cell) for cell in separators)
            ):
                continue
            index += 1
            while index < len(lines):
                row = _cells(lines[index])
                index += 1
                if len(row) < 2:
                    break
                if len(row) != len(headers) or not row[0] or all(_SEPARATOR.fullmatch(cell) for cell in row):
                    continue
                for column, value in enumerate(row[1:], start=1):
                    key = (fields[0], row[0].casefold(), fields[column])
                    cells[key].append((f"{row[0]} · {headers[column]}", value))
    return cells


def _quantity(value: str) -> tuple[Decimal, str, str] | None:
    match = _AMOUNT.fullmatch(value)
    if match is None:
        return None
    currency = (match["currency"] or "").casefold()
    unit = (match["unit"] or "").casefold()
    if _DURATION.fullmatch(unit):
        unit = unit.removesuffix("s")
    currency = {"us$": "usd", "ca$": "cad"}.get(currency, currency)
    if not currency and re.fullmatch(_CURRENCY, unit, re.IGNORECASE):
        currency, unit = unit, ""
    return Decimal(match["number"].replace(",", "")), currency, unit


def _compare_values(first: str, second: str) -> str:
    a, b = _quantity(first), _quantity(second)
    if a is not None and b is not None:
        if a[1:] != b[1:]:
            return "Different or unclear units"
        agrees = a[0] == b[0]
    elif (a is None) != (b is None):
        return "Different or unclear units"
    else:
        agrees = first.casefold() == second.casefold()
    return "Same stated value" if agrees else "Different stated values"


def compare_tables(question: str, documents: Mapping[str, Sequence[str]]) -> list[TableFinding]:
    """Pair cells by row key and column names. Preserve units and exact values."""
    if len(documents) != 2:
        return []
    first, second = (_table_cells(passages) for passages in documents.values())
    keys = list(dict.fromkeys([*first, *second]))
    normalized = " ".join(question.casefold().split())
    # Explicitly named rows take precedence in longer tables.
    named = [key for key in keys if re.search(rf"(?<!\w){re.escape(key[1])}(?!\w)", normalized)]
    findings = []
    for key in (named or keys)[:6]:
        left = first.get(key, [])
        right = second.get(key, [])
        label = (left or right)[0][0]
        a = (left[0][1] or None) if len(left) == 1 else None
        b = (right[0][1] or None) if len(right) == 1 else None
        if len(left) > 1 or len(right) > 1:
            status = "Ambiguous row"
        elif a is None or b is None:
            status = "Missing evidence"
        else:
            status = _compare_values(a, b)
        findings.append(TableFinding(label, a, b, status))
    return findings
