import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from nortpole.chat.evidence_relevance import sentence_spans
from nortpole.chat.verified_excerpts import _plain
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ContextFileMetadata

_PERIOD = re.compile(r"Reporting period: ([0-9]{4}-[0-9]{2}-[0-9]{2}) to ([0-9]{4}-[0-9]{2}-[0-9]{2})")
_SOURCES_PREFIX = "Knowledge sources: "
REPORTING_RENDERER_REVISION = "dated-excerpts-1"
_ISO_DATE = re.compile(r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}\b")
_DATE_HEADING = re.compile(r"(?:#{1,6}\s+)?([0-9]{4}-[0-9]{2}-[0-9]{2}):?")
_NEXT_STEPS = re.compile(r"\b(?:next steps?|follow[- ]?up|will|plans? to|scheduled to)\b", re.I)
_BLOCKERS = re.compile(r"\b(?:block(?:er|ers|ed|ing)|stall(?:ed|ing)|delayed|unable to)\b", re.I)
_METRICS = re.compile(r"[0-9]|\b(?:metrics?|volumes?|counts?|targets?|variance|throughput)\b", re.I)
_SECTIONS = ("Progress", "Metrics", "Blockers", "Next steps")
_MAX_PER_SOURCE = 4


@dataclass(frozen=True)
class ReportingRun:
    start: date
    end: date
    libraries: list[str]
    request: str

    @classmethod
    def from_message(cls, message: str, allowed_libraries: Collection[str]) -> "ReportingRun":
        # The two lines are part of the saved user message, so regenerating a
        # report always rechecks the original period and sources.
        period, _, rest = message.partition("\n")
        sources, separator, request = rest.partition("\n\n")
        match = _PERIOD.fullmatch(period)
        try:
            if not match or not sources.startswith(_SOURCES_PREFIX) or not separator or not request.strip():
                raise ValueError
            start, end = (date.fromisoformat(value) for value in match.groups())
            names = json.loads(sources.removeprefix(_SOURCES_PREFIX))
            if start > end or not isinstance(names, list) or not 0 < len(names) <= 100:
                raise ValueError
            if any(not isinstance(name, str) or not name for name in names):
                raise ValueError
        except (ValueError, RecursionError):
            raise NortPoleError(
                NortPoleErrorCode.INVALID_INPUT,
                "Choose a valid reporting period and at least one Knowledge source, then describe the report.",
            ) from None
        if not set(names).issubset(allowed_libraries):
            raise NortPoleError(
                NortPoleErrorCode.INSUFFICIENT_PERMISSIONS,
                "A selected Knowledge source is unavailable for this agent.",
            )
        return cls(start=start, end=end, libraries=list(dict.fromkeys(names)), request=request.strip())

    def _in_period(self, dates: list[str]) -> bool:
        try:
            return bool(dates) and all(self.start <= date.fromisoformat(value) <= self.end for value in dates)
        except ValueError:
            return False

    def _dated_quotes(self, text: str) -> list[tuple[str, str]]:
        quotes = []
        for block in re.split(r"\n\s*\n", text):
            heading, _, body = block.partition("\n")
            dated_heading = _DATE_HEADING.fullmatch(heading.strip())
            evidence = body if dated_heading else block
            for start, end in sentence_spans(evidence):
                quote = evidence[start:end].strip()
                dates = _ISO_DATE.findall(quote)
                if dated_heading:
                    dates.append(dated_heading[1])
                if not 0 < len(quote) <= 500 or not self._in_period(dates):
                    continue
                content = _ISO_DATE.sub("", quote)
                if not re.search(r"[^\W\d_]", content):
                    continue
                section = "Progress"
                if _BLOCKERS.search(content):
                    section = "Blockers"
                elif _NEXT_STEPS.search(content):
                    section = "Next steps"
                elif _METRICS.search(content):
                    section = "Metrics"
                if dated_heading:
                    quote = f"{dated_heading[1]}\n{quote}"
                quotes.append((section, quote))
                if len(quotes) == _MAX_PER_SOURCE:
                    return quotes
        return quotes

    def render(self, sources: list[ContextFileMetadata]) -> tuple[str, list[ContextFileMetadata]]:
        """Use the same source order as the isolated Chat turn's citation allocator."""
        sections: dict[str, list[str]] = {section: [] for section in _SECTIONS}
        used_sources = []
        used_ids: set[str] = set()
        for source in sources:
            if source.source_document is None or source.file_id in used_ids:
                continue
            quotes = self._dated_quotes(source.file_content)
            if not quotes:
                continue
            used_sources.append(source)
            used_ids.add(source.file_id)
            for section, quote in quotes:
                sections[section].append(f"- “{_plain(quote)}” [[{len(used_sources)}]]")

        lines = ["## Status report", "", f"Reporting period {self.start} through {self.end}, inclusive."]
        for section, quotes in sections.items():
            lines.extend(("", f"### {section}", *(quotes or ["No dated evidence found."])))
        lines.extend((
            "", "### Evidence gaps",
            "Requested metrics or details without a supporting excerpt remain unverified."
            if used_sources else "No dated excerpts from the selected Knowledge support a report for this period.",
        ))
        return "\n".join(lines), used_sources
