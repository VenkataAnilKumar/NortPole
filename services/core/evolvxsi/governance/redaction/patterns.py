"""Detectors for sensitive text. Each one is a pattern plus, where a number has a
checksum, a check that cuts false matches. Only what is listed here is caught:
people's names, addresses, and free-text secrets are not."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


def _luhn(digits: str) -> bool:
    total, flip = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if flip:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        flip = not flip
    return total % 10 == 0


def _card_ok(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    # A run of one repeated digit passes the checksum but is not a card.
    return 13 <= len(digits) <= 19 and len(set(digits)) > 1 and _luhn(digits)


def _iban_ok(raw: str) -> bool:
    s = re.sub(r"\s", "", raw).upper()
    if not 15 <= len(s) <= 34:
        return False
    moved = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in moved)
    return int(num) % 97 == 1


def _ssn_ok(raw: str) -> bool:
    a, g, _ = raw.split("-")
    return a not in ("000", "666") and not a.startswith("9") and g != "00"


@dataclass(frozen=True)
class Detector:
    kind: str
    pattern: re.Pattern[str]
    check: Callable[[str], bool] | None = None


# Order matters: longer, more specific shapes first so a card number is not read as a phone number.
DETECTORS: tuple[Detector, ...] = (
    Detector("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)),
    Detector("SECRET", re.compile(
        r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bxox[baprs]-[A-Za-z0-9-]{10,}\b"
        r"|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b|\bBearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    Detector("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")),
    Detector("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{2,4}){3,8}\b"), _iban_ok),
    Detector("CARD", re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])"), _card_ok),
    Detector("SSN", re.compile(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])"), _ssn_ok),
    Detector("PHONE", re.compile(
        r"(?<![\w+])(?:\+\d{1,3}[\s.-]?)(?:\(?\d{1,4}\)?[\s.-]?)\d{2,4}[\s.-]?\d{2,4}(?:[\s.-]?\d{2,4})?(?!\d)"
        r"|(?<![\w+])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")),
)
