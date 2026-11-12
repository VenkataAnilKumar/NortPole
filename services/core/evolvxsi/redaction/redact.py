from __future__ import annotations

from evolvxsi.redaction.patterns import DETECTORS


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Replace each match with [REDACTED:KIND]. Returns the new text and counts by kind."""
    counts: dict[str, int] = {}
    for det in DETECTORS:
        def repl(m, det=det):  # type: ignore[no-untyped-def]
            if det.check is not None and not det.check(m.group(0)):
                return m.group(0)
            counts[det.kind] = counts.get(det.kind, 0) + 1
            return f"[REDACTED:{det.kind}]"

        text = det.pattern.sub(repl, text)
    return text, counts
