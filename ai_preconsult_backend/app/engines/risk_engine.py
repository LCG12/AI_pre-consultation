from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.core.config_loader import get_red_flag_rules, get_yellow_flag_rules
from ai_preconsult_backend.app.engines.rule_engine import evaluate_condition
from ai_preconsult_backend.app.models.schemas import RuleHit
from ai_preconsult_backend.app.tools.state_tool import get_by_path


RISK_ORDER = {"unknown": 0, "green": 1, "yellow": 2, "red": 3}


def evaluate_risk(state: dict[str, Any]) -> tuple[str, list[RuleHit], bool]:
    hits: list[RuleHit] = []
    should_stop = False
    level = "green"

    for rule in get_red_flag_rules() + get_yellow_flag_rules():
        if evaluate_condition(state, rule["condition"]):
            hit = RuleHit(
                rule_id=rule["rule_id"],
                rule_name=rule["name"],
                risk_level=rule["risk_level"],
                reason=rule["reason"],
                trigger_field=rule["condition"]["field"],
                trigger_value=get_by_path(state, rule["condition"]["field"]),
            )
            hits.append(hit)
            if RISK_ORDER[rule["risk_level"]] > RISK_ORDER[level]:
                level = rule["risk_level"]
            should_stop = should_stop or bool(rule.get("should_stop_dialogue", False))

    return level, hits, should_stop
