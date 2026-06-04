from __future__ import annotations

import json
import os
from typing import Any

import httpx


ALLOWED_SLOT_KEYS = {
    "patient_basic_info.age",
    "patient_basic_info.gender",
    "patient_basic_info.pregnancy_status",
    "chief_complaint.raw_text",
    "chief_complaint.main_symptoms",
    "chief_complaint.duration_days",
    "slots.fever.duration_days",
    "slots.fever.max_temperature_c",
    "slots.fever.current_temperature_c",
    "slots.cough.has_cough",
    "slots.cough.cough_type",
    "slots.cough.sputum",
    "slots.abdominal_pain.location",
    "slots.abdominal_pain.pain_type",
    "slots.abdominal_pain.severity",
    "slots.abdominal_pain.duration_hours",
    "slots.abdominal_pain.radiation",
    "slots.abdominal_pain.onset",
    "slots.abdominal_pain.eating_relationship",
    "slots.abdominal_pain.bowel_movement",
    "slots.headache.onset_speed",
    "slots.headache.location",
    "slots.headache.pain_type",
    "slots.headache.severity",
    "slots.headache.duration_hours",
    "slots.headache.frequency",
    "slots.headache.red_flags.thunderclap_onset",
    "slots.headache.red_flags.neuro_symptoms",
    "slots.headache.red_flags.fever_stiff_neck",
    "slots.headache.red_flags.trauma_anticoag",
    "slots.headache.red_flags.new_onset_over_50",
    "slots.headache.red_flags.worsening_pattern",
    "slots.headache.red_flags.pregnancy_related",
    "slots.headache.red_flags.eye_symptoms",
    "slots.associated_symptoms.sore_throat",
    "slots.associated_symptoms.fatigue",
    "slots.associated_symptoms.headache",
    "slots.associated_symptoms.diarrhea",
    "slots.associated_symptoms.rash",
    "slots.associated_symptoms.nausea_vomiting",
    "slots.associated_symptoms.constipation",
    "slots.associated_symptoms.fever",
    "slots.associated_symptoms.photophobia",
    "slots.associated_symptoms.visual_aura",
    "slots.associated_symptoms.neck_pain",
    "slots.red_flags.shortness_of_breath",
    "slots.red_flags.chest_pain",
    "slots.red_flags.hemoptysis",
    "slots.red_flags.confusion",
    "slots.red_flags.seizure",
    "slots.red_flags.cyanosis",
    "slots.red_flags.peritoneal_signs",
    "slots.red_flags.hematemesis",
    "slots.red_flags.melena",
    "slots.red_flags.syncope",
    "slots.allergy_history.has_allergy",
    "slots.allergy_history.detail",
    "slots.medication_history.has_used_medicine",
    "slots.medication_history.detail",
}

ALLOWED_SYMPTOMS = {"fever", "cough", "sore_throat", "abdominal_pain", "headache"}

EXTRACTION_FUNCTION_NAME = "extract_preconsult_slots"

EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": EXTRACTION_FUNCTION_NAME,
        "description": (
            "从患者自然语言描述中抽取预问诊结构化字段。"
            "只提取患者明确提到的信息，不要猜测未提及的字段。"
            "数值含糊时直接提取合理估计值（如'几小时'→duration_hours=3，"
            "'一点点'→severity='mild'），不要列入 uncertain_fields。"
            "只有患者说'不确定''不知道'才列入 uncertain_fields。"
            "重要：患者明确否认必须设为 false！"
            "但只否定患者明确提到的那个字段，不要扩大到无关字段。"
            "例：问'有没有神经症状'，患者说'没有这些症状'\n"
            "  →只设 neuro_symptoms=false，不要同时把所有红旗都设 false。"
            "raw_evidence 里记录为否定的字段，必须同时输出 false 值。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chief_complaint": {
                    "type": "object",
                    "description": "患者主诉信息",
                    "properties": {
                        "raw_text": {"type": "string", "description": "患者原话原文"},
                        "main_symptoms": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(ALLOWED_SYMPTOMS)},
                            "description": "识别到的主诉症状",
                        },
                        "duration_days": {"type": "integer", "description": "症状持续天数"},
                        "path_id": {
                            "type": "string",
                            "enum": ["fever_cough_v1", "abdominal_pain_v1", "headache_v1"],
                            "description": "匹配的预问诊路径",
                        },
                    },
                },
                "patient_basic_info": {
                    "type": "object",
                    "description": "患者基本信息",
                    "properties": {
                        "age": {"type": "integer", "description": "年龄"},
                        "gender": {"type": "string", "enum": ["male", "female"], "description": "性别"},
                        "pregnancy_status": {"type": "boolean", "description": "是否怀孕或备孕"},
                    },
                },
                "fever_slots": {
                    "type": "object",
                    "description": "发热相关字段",
                    "properties": {
                        "duration_days": {"type": "integer", "description": "发热持续天数"},
                        "max_temperature_c": {"type": "number", "description": "最高体温（摄氏度）"},
                        "current_temperature_c": {"type": "number", "description": "当前体温（摄氏度）"},
                    },
                },
                "cough_slots": {
                    "type": "object",
                    "description": "咳嗽相关字段",
                    "properties": {
                        "has_cough": {"type": "boolean", "description": "是否有咳嗽"},
                        "cough_type": {"type": "string", "enum": ["dry", "productive", "none"], "description": "咳嗽类型"},
                        "sputum": {"type": "string", "enum": ["yellow", "white", "green", "bloody"], "description": "痰的颜色"},
                    },
                },
                "abdominal_pain_slots": {
                    "type": "object",
                    "description": "腹痛相关字段",
                    "properties": {
                        "location": {
                            "type": "string",
                            "enum": ["right_lower", "left_lower", "right_upper", "left_upper",
                                     "upper_abdomen", "lower_abdomen", "periumbilical", "diffuse"],
                            "description": "疼痛位置",
                        },
                        "pain_type": {
                            "type": "string",
                            "enum": ["colicky", "dull", "stabbing", "distension", "burning"],
                            "description": "疼痛性质",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["mild", "moderate", "severe"],
                            "description": "疼痛程度",
                        },
                        "duration_hours": {"type": "string", "description": "腹痛持续时长，如'3小时'、'几小时'、'一天'、'两天'等"},
                        "radiation": {"type": "string", "description": "放射部位，如 back/shoulder/none"},
                        "onset": {"type": "string", "enum": ["sudden", "gradual"], "description": "起病方式"},
                        "eating_relationship": {
                            "type": "string",
                            "enum": ["before_meal", "after_meal", "unrelated"],
                            "description": "与进食关系",
                        },
                        "bowel_movement": {
                            "type": "string",
                            "enum": ["normal", "diarrhea", "constipation", "bloody"],
                            "description": "大便变化",
                        },
                    },
                },
                "headache_slots": {
                    "type": "object",
                    "description": "头痛相关字段",
                    "properties": {
                        "onset_speed": {
                            "type": "string",
                            "enum": ["sudden", "gradual"],
                            "description": "起病速度，sudden=突然/几秒到几分钟达峰",
                        },
                        "location": {
                            "type": "string",
                            "enum": ["unilateral", "bilateral", "frontal", "temporal", "occipital", "periorbital", "vertex", "diffuse"],
                            "description": "头痛部位",
                        },
                        "pain_type": {
                            "type": "string",
                            "enum": ["pulsating", "pressing", "stabbing", "electric", "distension"],
                            "description": "疼痛性质，pulsating=搏动样，pressing=压迫样，stabbing=针刺样，electric=电击样",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["mild", "moderate", "severe"],
                            "description": "疼痛程度，severe=剧烈/一生中最严重的头痛",
                        },
                        "duration_hours": {"type": "string", "description": "每次头痛持续时长，如'3小时'、'几小时'、'半天'等"},
                        "frequency": {
                            "type": "string",
                            "enum": ["daily", "weekly", "monthly", "first_time"],
                            "description": "发作频率",
                        },
                        "red_flags": {
                            "type": "object",
                            "description": "头痛专属红旗信号",
                            "properties": {
                                "thunderclap_onset": {"type": "boolean", "description": "突然发生、几秒到几分钟达到最痛（雷击样头痛）"},
                                "neuro_symptoms": {"type": "boolean", "description": "一侧肢体无力/麻木、说话不清、复视、视野缺损"},
                                "fever_stiff_neck": {"type": "boolean", "description": "发热、颈部僵硬、意识改变"},
                                "trauma_anticoag": {"type": "boolean", "description": "近期头部外伤或正在服用抗凝药"},
                                "new_onset_over_50": {"type": "boolean", "description": "50 岁以后新发的头痛"},
                                "worsening_pattern": {"type": "boolean", "description": "头痛越来越重、越来越频繁"},
                                "pregnancy_related": {"type": "boolean", "description": "怀孕或产后新发头痛"},
                                "eye_symptoms": {"type": "boolean", "description": "红眼、眼痛、看灯有彩虹圈"},
                            },
                        },
                    },
                },
                "associated_symptoms": {
                    "type": "object",
                    "description": "伴随症状，均为布尔值",
                    "properties": {
                        "sore_throat": {"type": "boolean"},
                        "fatigue": {"type": "boolean"},
                        "headache": {"type": "boolean"},
                        "diarrhea": {"type": "boolean"},
                        "rash": {"type": "boolean"},
                        "nausea_vomiting": {"type": "boolean"},
                        "constipation": {"type": "boolean"},
                        "fever": {"type": "boolean"},
                        "photophobia": {"type": "boolean", "description": "怕光"},
                        "visual_aura": {"type": "boolean", "description": "视物闪光、暗点、视物模糊"},
                        "neck_pain": {"type": "boolean", "description": "颈肩痛"},
                    },
                },
                "red_flags": {
                    "type": "object",
                    "description": "红旗急症信号，均为布尔值",
                    "properties": {
                        "shortness_of_breath": {"type": "boolean"},
                        "chest_pain": {"type": "boolean"},
                        "hemoptysis": {"type": "boolean"},
                        "confusion": {"type": "boolean"},
                        "seizure": {"type": "boolean"},
                        "cyanosis": {"type": "boolean"},
                        "peritoneal_signs": {"type": "boolean"},
                        "hematemesis": {"type": "boolean"},
                        "melena": {"type": "boolean"},
                        "syncope": {"type": "boolean"},
                    },
                },
                "allergy_history": {
                    "type": "object",
                    "description": "过敏史",
                    "properties": {
                        "has_allergy": {"type": "boolean"},
                        "detail": {"type": "string", "description": "过敏原详情"},
                    },
                },
                "medication_history": {
                    "type": "object",
                    "description": "用药史",
                    "properties": {
                        "has_used_medicine": {"type": "boolean"},
                        "detail": {"type": "string", "description": "药名、剂量、效果等"},
                    },
                },
                "uncertain_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "提取了但不太确定的字段（使用 dot-notation，如 slots.fever.max_temperature_c）",
                },
                "raw_evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "text": {"type": "string", "description": "患者原话中对应的原文片段"},
                        },
                    },
                    "description": "每个字段对应的患者原话片段",
                },
            },
        },
    },
}

# Mapping from function-call nested keys to dot-notation prefixes
_NESTED_TO_FLAT: dict[str, str] = {
    "patient_basic_info": "patient_basic_info",
    "fever_slots": "slots.fever",
    "cough_slots": "slots.cough",
    "abdominal_pain_slots": "slots.abdominal_pain",
    "headache_slots": "slots.headache",
    "associated_symptoms": "slots.associated_symptoms",
    "red_flags": "slots.red_flags",
    "allergy_history": "slots.allergy_history",
    "medication_history": "slots.medication_history",
}


class LLMExtractionError(RuntimeError):
    pass


def extract_slots_with_llm(
    text: str,
    state: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    base_url = (os.getenv("PRECONSULT_LLM_BASE_URL") or "").strip().rstrip("/")
    model = os.getenv("PRECONSULT_LLM_MODEL", "").strip()
    api_key = os.getenv("PRECONSULT_LLM_API_KEY") or "".strip()
    timeout = timeout_seconds or float(os.getenv("PRECONSULT_LLM_TIMEOUT", "30"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(text, state or {})},
        ],
        "tools": [EXTRACTION_TOOL],
        "tool_choice": {"type": "function", "function": {"name": EXTRACTION_FUNCTION_NAME}},
        "temperature": 0,
        "max_tokens": 1200,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMExtractionError(f"LLM request failed: {exc}") from exc

    try:
        message = response.json()["choices"][0]["message"]
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # Fallback: model might return content instead of tool call
            content = message.get("content", "{}")
            parsed = _legacy_parse_json(content)
            return normalize_extraction_result(parsed, raw_text=text)
        arguments = tool_calls[0]["function"]["arguments"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMExtractionError("LLM response shape is invalid") from exc

    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise LLMExtractionError(f"Failed to parse function arguments: {exc}") from exc

    return normalize_extraction_result(parsed, raw_text=text)


def normalize_extraction_result(result: dict[str, Any], raw_text: str) -> dict[str, Any]:
    """Validate and flatten the nested function-call output to dot-notation slots."""
    normalized_slots: dict[str, Any] = {}

    # Chief complaint
    chief = result.get("chief_complaint")
    if isinstance(chief, dict):
        symptoms = chief.get("main_symptoms")
        if isinstance(symptoms, list):
            filtered = [s for s in symptoms if s in ALLOWED_SYMPTOMS]
            if filtered:
                normalized_slots["chief_complaint.main_symptoms"] = filtered
                normalized_slots["chief_complaint.raw_text"] = raw_text
        if chief.get("duration_days") is not None:
            normalized_slots["chief_complaint.duration_days"] = _safe_int(chief["duration_days"])

    def _flatten(value: Any, prefix: str) -> None:
        """Recursively flatten nested objects into dot-notation keys."""
        if not isinstance(value, dict):
            return
        for field, val in value.items():
            if val is None or val == "":
                continue
            flat_key = f"{prefix}.{field}"
            if isinstance(val, dict):
                _flatten(val, flat_key)
            elif flat_key in ALLOWED_SLOT_KEYS:
                if isinstance(val, bool):
                    normalized_slots[flat_key] = val
                elif isinstance(val, str) and val.strip():
                    normalized_slots[flat_key] = val
                elif isinstance(val, (int, float)):
                    normalized_slots[flat_key] = val

    for nested_key, flat_prefix in _NESTED_TO_FLAT.items():
        group = result.get(nested_key)
        if isinstance(group, dict):
            _flatten(group, flat_prefix)

    uncertain_fields = result.get("uncertain_fields")
    raw_evidence = result.get("raw_evidence")
    return {
        "extracted_slots": {k: v for k, v in normalized_slots.items() if v is not None},
        "uncertain_fields": uncertain_fields if isinstance(uncertain_fields, list) else [],
        "raw_evidence": raw_evidence if isinstance(raw_evidence, list) else [],
    }


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _system_prompt() -> str:
    from ai_preconsult_backend.app.configs.prompts import extraction_system
    return extraction_system()


def _user_prompt(text: str, state: dict[str, Any]) -> str:
    from ai_preconsult_backend.app.configs.prompts import extraction_user
    compact_state = json.dumps({
        "chief_complaint": state.get("chief_complaint", {}),
        "patient_basic_info": state.get("patient_basic_info", {}),
        "slots": state.get("slots", {}),
        "dialogue": state.get("dialogue", {}),
    }, ensure_ascii=False)
    return extraction_user(compact_state, text)


def _legacy_parse_json(content: str) -> dict[str, Any]:
    """Fallback parser when model returns content instead of tool call."""
    import re
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise LLMExtractionError("LLM did not return a JSON object")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise LLMExtractionError("LLM JSON is not an object")
    return parsed
