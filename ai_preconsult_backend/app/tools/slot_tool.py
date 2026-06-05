from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.core.config_loader import get_path_config
from ai_preconsult_backend.app.tools.state_tool import get_by_path


RESPIRATORY_RED_FLAG_GROUP = {
    "slots.red_flags.shortness_of_breath",
    "slots.red_flags.chest_pain",
    "slots.red_flags.hemoptysis",
}


def missing_required_slots(state: dict[str, Any]) -> list[str]:
    path_config = get_path_config(state.get("path_id", "fever_cough_v1"))
    dialogue = state.get("dialogue", {})
    skipped = set(dialogue.get("skipped_slots", []))
    skipped.update(dialogue.get("uncertain_slots", []))
    if "red_flag_respiratory_group" in skipped:
        skipped.update(RESPIRATORY_RED_FLAG_GROUP)

    required_slots = sorted(
        path_config["required_slots"],
        key=lambda item: item["priority"],
        reverse=True,
    )
    missing: list[str] = []
    for slot in required_slots:
        key = slot["key"]
        if key in skipped or _is_dependency_not_applicable(state, key):
            continue
        value = get_by_path(state, key)
        if value is None or value == "":
            missing.append(key)
    return missing


def plan_next_question(state: dict[str, Any]) -> str | None:
    skipped = set(state.get("dialogue", {}).get("skipped_slots", []))
    skipped.update(state.get("dialogue", {}).get("uncertain_slots", []))
    if "red_flag_respiratory_group" in skipped:
        skipped.update(RESPIRATORY_RED_FLAG_GROUP)
    missing = [s for s in missing_required_slots(state) if s not in skipped]
    if not missing:
        return None
    if RESPIRATORY_RED_FLAG_GROUP.intersection(missing):
        return "red_flag_respiratory_group"
    return missing[0]


def _is_dependency_not_applicable(state: dict[str, Any], key: str) -> bool:
    if key == "slots.medication_history.detail":
        return get_by_path(state, "slots.medication_history.has_used_medicine") is not True
    if key == "slots.allergy_history.detail":
        return get_by_path(state, "slots.allergy_history.has_allergy") is not True
    return False
