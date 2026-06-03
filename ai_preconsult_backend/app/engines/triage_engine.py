from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.core.config_loader import get_department_rules
from ai_preconsult_backend.app.engines.rule_engine import evaluate_condition


def recommend_departments(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    departments: list[str] = []
    reasons: list[str] = []

    for rule in get_department_rules():
        if evaluate_condition(state, rule["condition"]):
            for department in rule["departments"]:
                if department not in departments:
                    departments.append(department)
            reasons.append(rule["reason"])

    if not departments:
        departments.append("全科")
        reasons.append("当前信息不足，建议先由全科评估")

    return departments, reasons
