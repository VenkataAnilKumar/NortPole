"""Select and render excerpts from the current, authorized passages."""

import re
from collections.abc import Mapping
from itertools import pairwise

from nortpole.chat.evidence_relevance import LookupIntent, evidence_terms, lookup_intent, term_overlap
from nortpole.chat.verified_comparison import compare_passages, is_comparison_question
from nortpole.chat.verified_table_comparison import compare_tables
from nortpole.file_store.models import ContextFileMetadata

BRACKETS = str.maketrans({
    "[": "&#91;", "]": "&#93;", "【": "&#12304;", "】": "&#12305;",
    "［": "&#65339;", "］": "&#65341;",
})


def _plain(text: str) -> str:
    # Literal evidence can contain lookalike citations or Markdown links.
    text = text.translate(BRACKETS)
    return re.sub(r"([\\`*_{}<>!])", r"\\\1", " ".join(text.split()))


def _lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"(?<=[.!?])\s+|\n+", text) if line.strip()]


def _lookup_excerpt(lines: list[str], terms: set[str], intent: LookupIntent | None) -> str | None:
    # Adjacent sentences can state the subject and its rule separately.
    candidates = [*lines, *(f"{first} {second}" for first, second in pairwise(lines))]
    if intent is not None:
        candidates = [text for text in candidates if intent.supports(text)]
    ranking_terms = evidence_terms(intent.query) if intent is not None else terms
    best = max(candidates, key=lambda text: (
        term_overlap(ranking_terms, evidence_terms(text)), -len(text),
    ), default="")
    # Require more than half the possible overlap score. A single incidental
    # word in a multi-term question cannot stand in for supporting evidence.
    if best and (
        intent is not None or term_overlap(terms, evidence_terms(best)) >= max(2, len(terms) + 1)
    ):
        return best
    return None


def select_excerpts(
    question: str,
    sources: list[ContextFileMetadata],
    citation_numbers: Mapping[str, int],
    *,
    research: bool = False,
) -> str:
    comparing = is_comparison_question(question)
    terms = evidence_terms(question)
    intent = None if comparing else lookup_intent(question)
    by_document: dict[str, list[tuple[ContextFileMetadata, str]]] = {}
    authorized = [source for source in sources if source.file_id in citation_numbers]
    for source in authorized:
        text = source.file_content.strip()
        # A selected sentence can omit a qualification needed for a comparison.
        excerpt = text if comparing else _lookup_excerpt(_lines(text), terms, intent)
        if excerpt:
            by_document.setdefault(source.file_id, []).append((source, excerpt))
    if not by_document:
        if research:
            return "## Research brief\n\nThe configured Knowledge libraries returned no verified passages for this question."
        return "No verified passages are available for this analysis."

    output = ["## Research brief" if research else "## Evidence from the selected documents"]
    if not comparing:
        output.append("These excerpts contain matching evidence for your question.")
    elif research and len(by_document) == 1:
        output.append("Only one document is represented in the retrieved evidence. Other documents or revisions are unavailable for comparison.")
    elif research:
        output.append("This brief covers the retrieved passages. Details beyond them are unverified.")
    elif len(by_document) == 1:
        output.append("Only one selected document is available. Other documents or revisions are unavailable for comparison.")
    else:
        output.append("This comparison covers the selected passages. Details outside them are unavailable for this analysis.")

    if comparing and not research:
        tables = compare_tables(question, {
            file_id: [excerpt for _, excerpt in entries]
            for file_id, entries in by_document.items()
        })
        if tables:
            def cell(text: str) -> str:
                return _plain(text).replace("|", r"\|").replace("$", r"\$")

            first, second = by_document
            left = cell(by_document[first][0][0].filename)
            right = cell(by_document[second][0][0].filename)
            body = [f"| Row · field | {left} | {right} | Finding |", "| --- | --- | --- | --- |"]
            for row in tables:
                a = f"{cell(row.first)} [[{citation_numbers[first]}]]" if row.first else "Unavailable"
                b = f"{cell(row.second)} [[{citation_numbers[second]}]]" if row.second else "Unavailable"
                body.append(f"| {cell(row.label)} | {a} | {b} | {row.status} |")
            output.extend(("### Verified table comparison", "\n".join(body)))

    comparisons = compare_passages(question, {
        file_id: [line for _, excerpt in entries for line in _lines(excerpt)]
        for file_id, entries in by_document.items()
    }) if comparing else []
    if comparisons:
        output.append("### Verified comparison")
        for comparison in comparisons:
            if comparison.agrees:
                value = _plain(next(iter(comparison.values.values())))
                markers = " ".join(f"[[{citation_numbers[file_id]}]]" for file_id in comparison.values)
                output.append(f"- **{_plain(comparison.label)} — agreement.** {value} {markers}")
            else:
                values = "\n".join(
                    f"  - {_plain(by_document[file_id][0][0].filename)} — {_plain(value)} [[{citation_numbers[file_id]}]]"
                    for file_id, value in comparison.values.items()
                )
                output.append(f"- **{_plain(comparison.label)} — different stated values.**\n{values}")

    for file_id, entries in by_document.items():
        marker = f"[[{citation_numbers[file_id]}]]"
        output.append(f"### {_plain(entries[0][0].filename)}")
        excerpts = dict.fromkeys(_plain(excerpt) for _, excerpt in entries)
        output.extend(f"> {line} {marker}" for line in excerpts)
    return "\n\n".join(output)
