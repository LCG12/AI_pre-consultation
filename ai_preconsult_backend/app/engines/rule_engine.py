from __future__ import annotations

import re
from typing import Any

from ai_preconsult_backend.app.tools.state_tool import get_by_path


CN_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def evaluate_condition(state: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = condition["field"]
    actual = get_by_path(state, field)
    expected = condition.get("value")
    operator = condition["operator"]

    if actual is None:
        return False
    if operator == "equals":
        return actual == expected
    if operator in {">=", ">", "<=", "<"}:
        actual_number = _to_number(actual, field)
        expected_number = _to_number(expected, field)
        if actual_number is None or expected_number is None:
            return False
        if operator == ">=":
            return actual_number >= expected_number
        if operator == ">":
            return actual_number > expected_number
        if operator == "<=":
            return actual_number <= expected_number
        if operator == "<":
            return actual_number < expected_number
    if operator == "contains_any":
        if not isinstance(expected, list):
            return False
        if isinstance(actual, list):
            return any(item in actual for item in expected)
        if isinstance(actual, str):
            return any(str(item) in actual for item in expected)
        return False
    return False


def _to_number(value: Any, field: str) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    if "duration_hours" in field:
        return _parse_duration_hours(text)

    number = _extract_number(text)
    return float(number) if number is not None else None


def _parse_duration_hours(text: str) -> float | None:
    if "半天" in text:
        return 12.0

    match = re.search(r"([0-9]+(?:\.[0-9]+)?|[零一二两三四五六七八九十]+)\s*(天|日|小时|个?钟头|个?钟|h)?", text)
    if not match:
        return None

    number = _extract_number(match.group(1))
    if number is None:
        return None

    unit = match.group(2) or ""
    if unit in {"天", "日"}:
        return float(number) * 24
    return float(number)


def _extract_number(text: str) -> float | None:
    numeric = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
    if numeric:
        return float(numeric.group(0))

    if text == "半":
        return 0.5

    if text in CN_NUMBERS:
        return float(CN_NUMBERS[text])

    if text.startswith("十"):
        tail = text[1:]
        return float(10 + CN_NUMBERS.get(tail, 0))

    if "十" in text:
        head, tail = text.split("十", 1)
        return float(CN_NUMBERS.get(head, 0) * 10 + CN_NUMBERS.get(tail, 0))

    return None
