"""Deterministic checks for provider-authored assessment explanation text."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_WHITESPACE_RE = re.compile(r"\s+")
_PROTECTED_ATTRIBUTE_RE = re.compile(
    r"(?ix)\b(?:"
    r"age|aged|date\s+of\s+birth|dob|"
    r"sex|gender|pregnan(?:t|cy)|sexual\s+orientation|"
    r"race|racial|ethnicity|ethnic|nationality|citizenship|"
    r"religion|religious|political\s+(?:view|views|belief|beliefs)|"
    r"disability|disabled|health|medical\s+(?:condition|conditions)|"
    r"marital\s+status|family\s+status"
    r")\b"
)
_QUOTED_TEXT_RE = re.compile(r'["“”]([^"“”]{2,200})["“”]')
_NUMBER_WORDS = {
    "zero": Decimal("0"),
    "one": Decimal("1"),
    "two": Decimal("2"),
    "three": Decimal("3"),
    "four": Decimal("4"),
    "five": Decimal("5"),
    "six": Decimal("6"),
    "seven": Decimal("7"),
    "eight": Decimal("8"),
    "nine": Decimal("9"),
    "ten": Decimal("10"),
    "eleven": Decimal("11"),
    "twelve": Decimal("12"),
    "thirteen": Decimal("13"),
    "fourteen": Decimal("14"),
    "fifteen": Decimal("15"),
    "sixteen": Decimal("16"),
    "seventeen": Decimal("17"),
    "eighteen": Decimal("18"),
    "nineteen": Decimal("19"),
    "twenty": Decimal("20"),
}
_NUMBER_TOKEN = r"(?:\d+(?:[.,]\d+)?|" + "|".join(_NUMBER_WORDS) + r")"
_MEASURED_CLAIM_RE = re.compile(
    rf"(?ix)\b(?P<number>{_NUMBER_TOKEN})\s*\+?\s*"
    r"(?P<unit>years?|yrs?|months?|percent|%)(?!\w)"
)


def normalize_explanation_text(value: str) -> str:
    return _WHITESPACE_RE.sub(
        " ", unicodedata.normalize("NFKC", value).strip()
    ).casefold()


def contains_protected_attribute_language(values: list[str] | tuple[str, ...]) -> bool:
    """Return true only for explicit protected/sensitive attribute terminology."""
    return any(_PROTECTED_ATTRIBUTE_RE.search(value) for value in values)


def quoted_claims(value: str) -> tuple[str, ...]:
    return tuple(
        normalize_explanation_text(match.group(1))
        for match in _QUOTED_TEXT_RE.finditer(value)
    )


def measured_claims(value: str) -> tuple[tuple[Decimal, str], ...]:
    claims: list[tuple[Decimal, str]] = []
    for match in _MEASURED_CLAIM_RE.finditer(value):
        number_text = match.group("number").casefold()
        try:
            number = (
                _NUMBER_WORDS[number_text]
                if number_text in _NUMBER_WORDS
                else Decimal(number_text.replace(",", "."))
            )
        except InvalidOperation:
            continue
        unit = match.group("unit").casefold()
        if unit in {"year", "years", "yr", "yrs"}:
            unit = "years"
        elif unit in {"month", "months"}:
            unit = "months"
        else:
            unit = "percent"
        claims.append((number.normalize(), unit))
    return tuple(claims)
