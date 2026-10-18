"""Deterministic normalization and validation for bridge field values."""

from __future__ import annotations

import re
from typing import Any

from .utils import normalize_text, parse_number

UNIT_TO_METERS = {
    "m": 1.0,
    "米": 1.0,
    "cm": 0.01,
    "厘米": 0.01,
    "mm": 0.001,
    "毫米": 0.001,
}
CARRIAGEWAY_ALIASES = {
    "上行线": "上行",
    "上行": "上行",
    "下行线": "下行",
    "下行": "下行",
    "左幅": "左幅",
    "右幅": "右幅",
    "双幅": "双幅",
    "跨线": "跨线",
}
_NUM = r"\d+(?:\.\d+)?"
_SPAN_TERM_RE = re.compile(rf"({_NUM})\s*[x×*]\s*({_NUM})")
_SPAN_SINGLE_RE = re.compile(rf"^\s*({_NUM})\s*(cm|厘米|mm|毫米|m|米)?\s*$")


def _clean_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else float(value)


def _resolve_unit(unit: str | None) -> tuple[str, float]:
    key = normalize_text(unit).lower()
    if key in UNIT_TO_METERS:
        return ("m", UNIT_TO_METERS[key])
    return ("m", 1.0)


def normalize_chainage(value: Any) -> tuple[Any, str | None]:
    text = normalize_text(value).upper().replace(" ", "")
    match = re.search(r"K?(\d+(?:\.\d+)?)\+(\d+(?:\.\d+)?)", text)
    if match:
        kilometres = float(match.group(1))
        metres = float(match.group(2))
        return _clean_number(kilometres * 1000 + metres), "m"
    number = parse_number(text)
    return (_clean_number(number), "m") if number is not None else (value, None)


def normalize_measurement(
    value: Any,
    normalized_value: Any,
    unit: str | None,
) -> tuple[Any, str | None]:
    source = normalized_value if parse_number(normalized_value) is not None else value
    number = parse_number(source)
    if number is None:
        return normalized_value, unit
    canonical_unit, factor = _resolve_unit(unit)
    return _clean_number(number * factor), canonical_unit


def normalize_span_combination(
    value: Any,
    normalized_value: Any,
    unit: str | None,
) -> tuple[Any, str | None]:
    text = normalize_text(normalized_value) or normalize_text(value)
    text = text.replace("×", "*").replace("x", "*").replace("X", "*")
    if not text:
        return normalized_value, unit
    canonical_unit, factor = _resolve_unit(unit)
    terms: list[str] = []
    for count, span in _SPAN_TERM_RE.findall(text):
        count_value = float(count)
        span_value = float(span) * factor
        if not count_value.is_integer() or count_value < 1:
            return normalized_value, unit
        terms.append(f"{int(count_value)}*{_clean_number(span_value)}")
    if terms:
        return "+".join(terms), "m"
    single = _SPAN_SINGLE_RE.fullmatch(text)
    if single:
        span_value = float(single.group(1))
        embedded_unit = single.group(2) or unit
        _, embedded_factor = _resolve_unit(embedded_unit)
        return _clean_number(span_value * embedded_factor), "m"
    return normalized_value, unit


def normalize_field_value(
    field_code: str,
    value: Any,
    normalized_value: Any,
    unit: str | None,
) -> tuple[Any, str | None]:
    if field_code == "D":
        return normalize_chainage(normalized_value or value)
    if field_code == "E":
        raw = normalize_text(normalized_value or value)
        return CARRIAGEWAY_ALIASES.get(raw, raw or normalized_value), unit
    if field_code in {"F", "H", "N", "O", "P", "R", "S"}:
        return normalize_measurement(value, normalized_value, unit)
    if field_code == "G":
        return normalize_span_combination(value, normalized_value, unit)
    return normalized_value, unit


def parse_span_combination(value: Any, unit: str | None = "m") -> list[float]:
    canonical, _ = normalize_span_combination(value, value, unit)
    if canonical is None:
        return []
    text = str(canonical).replace("×", "*").replace("x", "*").replace("X", "*")
    spans: list[float] = []
    for part in text.split("+"):
        match = re.fullmatch(rf"\s*(\d+)\*({_NUM})\s*", part)
        if not match:
            continue
        count = int(match.group(1))
        span = float(match.group(2))
        spans.extend([span] * count)
    return spans


def span_total(value: Any, unit: str | None = "m") -> float | None:
    spans = parse_span_combination(value, unit)
    return sum(spans) if spans else None
