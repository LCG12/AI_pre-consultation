from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.tools.state_tool import get_by_path


def evaluate_condition(state: dict[str, Any], condition: dict[str, Any]) -> bool:
    actual = get_by_path(state, condition["field"])
    expected = condition.get("value")
    operator = condition["operator"]

    if actual is None:
        return False
    if operator == "equals":
        return actual == expected
    if operator == ">=":
        return actual >= expected
    if operator == ">":
        return actual > expected
    if operator == "<=":
        return actual <= expected
    if operator == "<":
        return actual < expected
    if operator == "contains_any":
        if not isinstance(actual, list):
            return False
        return any(item in actual for item in expected)
    return False
