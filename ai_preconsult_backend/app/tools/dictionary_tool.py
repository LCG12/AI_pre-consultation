from __future__ import annotations

import re
from typing import Any

from ai_preconsult_backend.app.core.config_loader import get_dictionary


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


def _cn_to_int(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    if text in CN_NUMBERS:
        return CN_NUMBERS[text]
    if text.startswith("十"):
        tail = text[1:]
        return 10 + CN_NUMBERS.get(tail, 0)
    if "十" in text:
        head, tail = text.split("十", 1)
        return CN_NUMBERS.get(head, 0) * 10 + CN_NUMBERS.get(tail, 0)
    return None


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _has_negation_near(text: str, keyword: str) -> bool:
    index = text.find(keyword)
    if index < 0:
        return False
    prefix = text[max(0, index - 4) : index]
    return any(token in prefix for token in ["没有", "没", "无", "否认", "不"])


def extract_by_dictionary(text: str) -> dict[str, Any]:
    dictionary = get_dictionary()
    extracted: dict[str, Any] = {}

    symptoms = []
    for symptom, words in dictionary["chief_complaint"].items():
        if _contains_any(text, words):
            symptoms.append(symptom)
    if symptoms:
        extracted["chief_complaint.main_symptoms"] = symptoms
        extracted["chief_complaint.raw_text"] = text
    if "fever" in symptoms:
        extracted["slots.fever.duration_days"] = _extract_duration_days(text)
    if "cough" in symptoms:
        extracted["slots.cough.has_cough"] = True
    if "sore_throat" in symptoms:
        extracted["slots.associated_symptoms.sore_throat"] = True
    if "abdominal_pain" in symptoms:
        extracted["slots.abdominal_pain.duration_hours"] = _extract_duration_hours(text)

    temperature = _extract_temperature(text)
    if temperature is not None:
        extracted["slots.fever.max_temperature_c"] = temperature

    age = _extract_age(text)
    if age is not None:
        extracted["patient_basic_info.age"] = age

    if any(word in text for word in ["怀孕", "孕妇", "孕期"]):
        extracted["patient_basic_info.pregnancy_status"] = True

    for field, words in dictionary["red_flags"].items():
        for word in words:
            if word in text:
                extracted[f"slots.red_flags.{field}"] = not _has_negation_near(text, word)
                break

    if any(word in text for word in ["不知道", "不确定", "说不清"]):
        extracted["_uncertain"] = True

    return {key: value for key, value in extracted.items() if value is not None}


def detect_red_flags(text: str) -> dict[str, bool]:
    dictionary = get_dictionary()
    hits: dict[str, bool] = {}
    for field, words in dictionary["red_flags"].items():
        for word in words:
            if word in text and not _has_negation_near(text, word):
                hits[field] = True
                break
    return hits


def detect_safety_issue(text: str) -> bool:
    dictionary = get_dictionary()
    return any(_contains_any(text, words) for words in dictionary["safety"].values())


def _extract_duration_days(text: str) -> int | None:
    match = re.search(r"([0-9一二两三四五六七八九十]+)\s*(天|日)", text)
    if not match:
        return None
    return _cn_to_int(match.group(1))


def _extract_temperature(text: str) -> float | None:
    match = re.search(r"([3-4][0-9])(?:\.|点)?([0-9])?\s*(?:度|℃)\s*([0-9])?", text)
    if not match:
        return None
    integer = match.group(1)
    decimal = match.group(2) or match.group(3)
    return float(f"{integer}.{decimal}") if decimal else float(integer)


def _extract_age(text: str) -> int | None:
    match = re.search(r"([0-9一二两三四五六七八九十]+)\s*岁", text)
    if not match:
        return None
    return _cn_to_int(match.group(1))


def _extract_duration_hours(text: str) -> float | None:
    match = re.search(r"([0-9一二两三四五六七八九十]+)\s*(?:小时|个?钟头|个?钟|h)", text)
    if match:
        num = _cn_to_int(match.group(1))
        return float(num) if num is not None else None
    match = re.search(r"([0-9]+)\s*(?:天)", text)
    if match:
        return float(match.group(1)) * 24
    return None
