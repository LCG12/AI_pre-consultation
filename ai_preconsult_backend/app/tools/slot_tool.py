from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.core.config_loader import get_path_config
from ai_preconsult_backend.app.tools.state_tool import get_by_path


def missing_required_slots(state: dict[str, Any]) -> list[str]:
    path_config = get_path_config(state.get("path_id", "fever_cough_v1"))
    required_slots = sorted(
        path_config["required_slots"],
        key=lambda item: item["priority"],
        reverse=True,
    )
    missing: list[str] = []
    for slot in required_slots:
        value = get_by_path(state, slot["key"])
        if value is None or value == "":
            missing.append(slot["key"])
    return missing


def plan_next_question(state: dict[str, Any]) -> str | None:
    skipped = set(state.get("dialogue", {}).get("skipped_slots", []))
    missing = [s for s in missing_required_slots(state) if s not in skipped]
    if not missing:
        return None
    red_group = {
        "slots.red_flags.shortness_of_breath",
        "slots.red_flags.chest_pain",
        "slots.red_flags.hemoptysis",
    }
    if red_group.intersection(missing):
        return "red_flag_respiratory_group"
    return missing[0]
