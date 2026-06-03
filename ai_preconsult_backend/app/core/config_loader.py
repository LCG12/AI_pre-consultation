from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "configs"


def load_json(relative_path: str) -> Any:
    path = CONFIG_DIR / relative_path
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=32)
def get_path_config(path_id: str = "fever_cough_v1") -> dict[str, Any]:
    return load_json(f"paths/{path_id}.json")


@lru_cache(maxsize=1)
def get_red_flag_rules() -> list[dict[str, Any]]:
    return load_json("rules/red_flags.json")


@lru_cache(maxsize=1)
def get_yellow_flag_rules() -> list[dict[str, Any]]:
    return load_json("rules/yellow_flags.json")


@lru_cache(maxsize=1)
def get_department_rules() -> list[dict[str, Any]]:
    return load_json("rules/department_rules.json")


@lru_cache(maxsize=1)
def get_dictionary() -> dict[str, Any]:
    return load_json("dictionaries/symptom_dictionary.json")


@lru_cache(maxsize=1)
def get_question_templates() -> dict[str, str]:
    return load_json("templates/question_templates.json")


@lru_cache(maxsize=1)
def get_patient_report_templates() -> dict[str, str]:
    return load_json("templates/patient_report_templates.json")
