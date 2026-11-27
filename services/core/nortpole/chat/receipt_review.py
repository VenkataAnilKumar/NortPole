"""Evaluate a single, explicit USD receipt rule against an attached CSV."""

import csv
import io
import re
from decimal import Decimal

from pydantic import BaseModel

from nortpole.file_store.models import ContextFileMetadata

_AMOUNT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_MONEY = rf"(?:\$\s*(?P<dollars>{_AMOUNT})|(?P<usd>{_AMOUNT})\s*(?:USD|dollars))"
_RULE = re.compile(
    rf"(?:expenses|charges|purchases)\s+"
    rf"(?P<comparison>(?:strictly\s+)?(?:over|above|more than|greater than)|at least)\s+"
    rf"{_MONEY}\s+(?:require|must have)\s+(?:a\s+)?receipt",
    re.IGNORECASE,
)
_EXEMPTION = re.compile(
    rf"(?:expenses|charges|purchases)\s+(?:of\s+)?{_MONEY}"
    r"\s+or\s+(?P<comparison>less|lower)\s+do not require\s+(?:a\s+)?receipt",
    re.IGNORECASE,
)
_REVIEW = re.compile(r"\b(?:violat\w*|complian\w*|compl(?:y|ies)|audit|check|apply|compare|flag|review)\b", re.I)
_ROW_ID = re.compile(r"[\w.-]{1,60}")
_POSITIVE = {"yes", "true", "provided", "attached", "present"}
_NEGATIVE = {"no", "false", "missing", "not attached", "absent"}


class ReceiptRow(BaseModel):
    row_id: str
    amount: Decimal
    has_receipt: bool


class ReceiptReview(BaseModel):
    source_id: str | None = None
    threshold: Decimal | None = None
    inclusive: bool = False
    rows: list[ReceiptRow] = []
    clarification: str | None = None

    def answer(self, citation_number: int | None = None) -> str:
        if self.clarification:
            return self.clarification
        assert self.threshold is not None
        comparator = "at or above" if self.inclusive else "over"
        citation = f" [[{citation_number}]]" if citation_number is not None else ""
        lines = [f"Expenses {comparator} {_dollars(self.threshold)} require a receipt.{citation}"]
        violations = []
        for row in self.rows:
            requires_receipt = (
                row.amount >= self.threshold if self.inclusive else row.amount > self.threshold
            )
            if requires_receipt and not row.has_receipt:
                violations.append(row.row_id)
                result = "Violation. A receipt is required and none is recorded."
            elif requires_receipt:
                result = "Complies. A receipt is required and one is recorded."
            else:
                result = "Complies. The amount falls outside the receipt requirement."
            lines.append(f"| `{row.row_id}` | {_dollars(row.amount)} | {result} |")
        summary = (
            "**Violations** · " + ", ".join(f"`{row_id}`" for row_id in violations)
            if violations
            else "**Violations** · None"
        )
        return "\n".join([
            lines[0],
            "",
            summary,
            "",
            "| Row | Amount | Receipt check |",
            "| --- | ---: | --- |",
            *lines[1:],
        ])


def _dollars(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _threshold(match: re.Match[str]) -> Decimal:
    return Decimal((match["dollars"] or match["usd"]).replace(",", ""))


def _read_rule(text: str, title: str) -> tuple[Decimal, bool] | None:
    rules: set[tuple[Decimal, bool]] = set()
    exemptions: set[Decimal] = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = sentence.strip(" \t.!")
        if re.fullmatch(re.escape(title) + r"(?:, version [\d.]+)?", sentence, re.I):
            continue
        if re.search(r"\b(?:exceptions?|except|unless|waiv\w*|exempt\w*|however)\b", sentence, re.I):
            return None
        if not re.search(r"\breceipts?\b", sentence, flags=re.I):
            continue
        rule = _RULE.fullmatch(sentence)
        if rule:
            rules.add((_threshold(rule), rule["comparison"].lower() == "at least"))
            continue
        exemption = _EXEMPTION.fullmatch(sentence)
        if exemption:
            exemptions.add(_threshold(exemption))
            continue
        return None
    if len(rules) != 1:
        return None
    threshold, inclusive = next(iter(rules))
    if exemptions and (inclusive or exemptions != {threshold}):
        return None
    return threshold, inclusive


def _read_rows(text: str) -> list[ReceiptRow]:
    reader = csv.DictReader(io.StringIO(text), strict=True)
    fields = {
        re.sub(r"[^a-z0-9]+", "_", name.strip().lower()): name
        for name in reader.fieldnames or []
    }
    if len(fields) != len(reader.fieldnames or []):
        raise ValueError("headers must be unique")
    amount_key = fields.get("amount_usd")
    receipt_key = next((fields[key] for key in ("receipt", "has_receipt", "receipt_present") if key in fields), None)
    id_key = fields.get("row_id") or fields.get("id")
    if amount_key is None or receipt_key is None:
        raise ValueError("missing required columns")

    rows: list[ReceiptRow] = []
    ids: set[str] = set()
    for index, row in enumerate(reader, start=1):
        row_id = (row.get(id_key) or "").strip() if id_key else str(index)
        amount = (row.get(amount_key) or "").strip().removeprefix("$").strip()
        receipt = (row.get(receipt_key) or "").strip().lower()
        if (
            None in row
            or not _ROW_ID.fullmatch(row_id)
            or row_id in ids
            or not re.fullmatch(_AMOUNT, amount)
            or receipt not in _POSITIVE | _NEGATIVE
        ):
            raise ValueError(f"invalid row {index}")
        rows.append(ReceiptRow(
            row_id=row_id,
            amount=Decimal(amount.replace(",", "")),
            has_receipt=receipt in _POSITIVE,
        ))
        ids.add(row_id)
    if not rows:
        raise ValueError("no data rows")
    return rows


def prepare_receipt_review(
    query: str,
    selected_sources: list[ContextFileMetadata],
    *,
    attached_csv_count: int = 1,
    policy_title: str | None = None,
) -> ReceiptReview | None:
    """Recognize a receipt review and return either a calculation or a clarification."""
    if policy_title is None and (
        not re.search(r"\breceipts?\b", query, re.I) or not _REVIEW.search(query)
    ):
        return None
    csvs = [item for item in selected_sources if item.source_document is None and item.filename.lower().endswith(".csv")]
    if attached_csv_count != 1 or len(csvs) != 1:
        return ReceiptReview(clarification="Attach one small CSV with an amount_usd column and a receipt column marked yes or no.")
    knowledge = [item for item in selected_sources if item.source_document is not None]
    # Match the actual title from retrieval if the question names the policy.
    named = [
        item for item in knowledge
        if re.search(r"(?<!\w)" + re.escape(item.filename) + r"(?!\w)", query, re.I)
    ]
    if policy_title:
        passages = [
            item for item in knowledge
            if item.filename.casefold() == policy_title.casefold()
        ]
        if not passages:
            return ReceiptReview(clarification=(
                "I couldn't find that policy title in the selected Knowledge library. "
                "Check the title and try again."
            ))
    else:
        passages = knowledge if policy_title is not None else named or knowledge
    document_ids = {item.file_id for item in passages}
    rules = {_read_rule(item.file_content, item.filename) for item in passages}
    if len(document_ids) != 1 or len(rules) != 1 or None in rules:
        return ReceiptReview(clarification=(
            "Which receipt rule should I apply? Select a policy with one explicit USD threshold "
            "and clarify whether expenses equal to the threshold require a receipt."
        ))
    try:
        rows = _read_rows(csvs[0].file_content)
    except (csv.Error, ValueError):
        return ReceiptReview(clarification=(
            "Provide a CSV with valid USD amounts in amount_usd, explicit yes or no values "
            "in receipt, and unique row IDs if an ID column is included."
        ))
    rule = next(iter(rules))
    assert rule is not None
    threshold, inclusive = rule
    return ReceiptReview(
        source_id=next(iter(document_ids)),
        threshold=threshold,
        inclusive=inclusive,
        rows=rows,
    )
