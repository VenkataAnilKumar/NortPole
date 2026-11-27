"""Rank literal evidence against the topics in a question."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

from nortpole.natural_language_processing.english_stopwords import ENGLISH_STOPWORDS_SET

_WORDS = re.compile(r"\b[^\W_]+\b")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_TOPIC_BREAK = re.compile(
    r"(?<=[.!?])\s+|,?\s+and\s+(?=(?:who|what|when|where|why|how|which)\b)",
    re.IGNORECASE,
)
_TOPIC_INTRO = re.compile(r"^(?:compare|contrast)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LookupIntent:
    query: str
    question: tuple[re.Pattern[str], ...]
    evidence: tuple[re.Pattern[str], ...]

    def supports(self, text: str) -> bool:
        return all(pattern.search(text) for pattern in self.evidence)


_LOOKUP_INTENTS = (
    LookupIntent(
        query="When does Search recheck access during follow-up retrieval and opening a resource?",
        question=(
            re.compile(r"\b(?:access|permissions?|can view|can open)\b", re.I),
            re.compile(r"\b(?:recheck\w*|evaluated again|checked again|validat\w*|reauthoriz\w*)\b", re.I),
            re.compile(r"\b(?:follow[- ]up|later message|initial search result|returns? to a result|opening (?:an?|the) (?:resource|item))\b", re.I),
        ),
        evidence=(
            re.compile(r"\b(?:recheck\w*|reauthoriz\w*|revalidat\w*|check\w* again)\b", re.I),
            re.compile(r"\b(?:follow[- ]up|later (?:message|request)|continuation)\b", re.I),
            re.compile(r"\b(?:resource open|open(?:ing)? (?:an?|the) (?:resource|result|item)|navigation)\b", re.I),
        ),
    ),
    LookupIntent(
        query="Does saving a task draft dispatch work or must the practitioner explicitly start a run?",
        question=(
            re.compile(r"\b(?:sav\w*|draft\w*|compos\w*)\b", re.I),
            re.compile(r"\b(?:dispatch\w*|start\w*|begin\w*|execut\w*|kick(?:ing)? off|get it underway)\b", re.I),
            re.compile(r"\b(?:task|draft|workflow|request|practitioner)\b", re.I),
        ),
        evidence=(
            re.compile(r"\b(?:sav\w*|draft\w*)\b", re.I),
            re.compile(
                r"\b(?:explicitly starts? (?:a|the) run|dispatch(?:es)? no work|"
                r"does not (?:start|execute|dispatch)\b|starts? only (?:when|after))\b",
                re.I,
            ),
        ),
    ),
)


def lookup_intent(question: str) -> LookupIntent | None:
    return next((
        intent for intent in _LOOKUP_INTENTS
        if all(pattern.search(question) for pattern in intent.question)
    ), None)


def comparison_topics(question: str) -> list[str]:
    parts = [part.strip() for part in _TOPIC_BREAK.split(question) if part.strip()]
    topics = list(dict.fromkeys(part for part in parts if not _TOPIC_INTRO.match(part)))
    return topics[:3] if len(parts) > 1 and topics else [question]


def evidence_terms(text: str) -> set[str]:
    words = set(_WORDS.findall(text.casefold())) - ENGLISH_STOPWORDS_SET
    return {word[:-1] if len(word) > 4 and word.endswith("s") else word for word in words}


def evidence_phrases(text: str) -> set[tuple[str, str]]:
    words = _WORDS.findall(text.casefold())
    return {
        (first, second) for first, second in pairwise(words)
        if first not in ENGLISH_STOPWORDS_SET and second not in ENGLISH_STOPWORDS_SET
    }


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        if text[start:match.start()].strip():
            spans.append((start, match.start()))
        start = match.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def term_overlap(topic: set[str], passage: set[str]) -> int:
    exact = topic & passage
    # A smaller prefix match covers inflections such as revoked and revocation.
    prefixes = {word[:4] for word in passage if len(word) >= 6}
    return 2 * len(exact) + sum(
        len(word) >= 6 and word[:4] in prefixes for word in topic - exact
    )


def fitting_passage_span(
    text: str, question: str, token_counter: Callable[[str], int], budget: int,
) -> tuple[int, int] | None:
    if token_counter(text.strip()) <= budget:
        return (0, len(text))

    spans = sentence_spans(text)
    terms = evidence_terms(question)
    ranked = sorted(
        spans,
        key=lambda span: -term_overlap(terms, evidence_terms(text[span[0]:span[1]])),
    )
    for start, end in ranked:
        if token_counter(text[start:end].strip()) <= budget:
            return start, end
    return None
