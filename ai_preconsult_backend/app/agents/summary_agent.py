from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class LLMSummaryError(RuntimeError):
    pass


def generate_doctor_summary(
    state: dict[str, Any],
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    base_url = os.getenv("PRECONSULT_LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    model = os.getenv("PRECONSULT_LLM_MODEL", "deepseek-chat").strip()
    api_key = os.getenv("PRECONSULT_LLM_API_KEY") or "".strip()
    timeout = timeout_seconds or float(os.getenv("PRECONSULT_LLM_TIMEOUT", "30"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(state)},
        ],
        "temperature": 0,
        "max_tokens": 800,
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
        raise LLMSummaryError(f"LLM request failed: {exc}") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMSummaryError("LLM response shape is invalid") from exc

    return _parse_json_object(content)


def build_fallback_summary(state: dict[str, Any]) -> dict[str, Any]:
    """Template-based fallback when LLM is unavailable."""
    chief = state.get("chief_complaint", {})
    slots = state.get("slots", {})
    patient = state.get("patient_basic_info", {})
    risk = state.get("risk", {})
    dialogue = state.get("dialogue", {})

    raw_text = chief.get("raw_text", "")
    symptoms = chief.get("main_symptoms", [])
    duration = chief.get("duration_days")

    symptom_labels = {"fever": "发热", "cough": "咳嗽", "sore_throat": "咽痛"}
    symptom_text = "、".join(symptom_labels.get(s, s) for s in symptoms) if symptoms else "待明确"

    findings: list[str] = []
    fever = slots.get("fever", {})
    if isinstance(fever, dict):
        if fever.get("max_temperature_c"):
            findings.append(f"最高体温 {fever['max_temperature_c']}°C")
        if fever.get("duration_days"):
            findings.append(f"发热持续 {fever['duration_days']} 天")

    cough = slots.get("cough", {})
    if isinstance(cough, dict):
        cough_type_map = {"dry": "干咳", "productive": "有痰", "none": "无咳嗽"}
        if cough.get("has_cough") is True:
            ct = cough_type_map.get(cough.get("cough_type", ""), "")
            findings.append(f"咳嗽 ({ct})" if ct else "有咳嗽")
            if cough.get("sputum"):
                sputum_map = {"yellow": "黄痰", "white": "白痰", "green": "绿痰", "bloody": "血丝痰"}
                findings.append(f"痰液: {sputum_map.get(cough['sputum'], cough['sputum'])}")

    assoc = slots.get("associated_symptoms", {})
    if isinstance(assoc, dict):
        assoc_labels = {
            "sore_throat": "咽痛", "fatigue": "乏力", "headache": "头痛",
            "diarrhea": "腹泻", "rash": "皮疹",
        }
        for key, label in assoc_labels.items():
            if assoc.get(key) is True:
                findings.append(label)

    red_flags = slots.get("red_flags", {})
    if isinstance(red_flags, dict):
        rf_labels = {
            "shortness_of_breath": "呼吸困难", "chest_pain": "胸痛", "hemoptysis": "咳血",
            "confusion": "意识模糊", "seizure": "抽搐", "cyanosis": "发绀",
        }
        positive_rf = [rf_labels[k] for k, v in red_flags.items() if v is True and k in rf_labels]
        if positive_rf:
            findings.append(f"红旗信号: {'、'.join(positive_rf)}")

    allergy = slots.get("allergy_history", {})
    medication = slots.get("medication_history", {})

    risk_level = risk.get("current_level", "unknown")
    risk_labels = {"red": "红旗（紧急）", "yellow": "黄旗（需关注）", "green": "绿旗（低风险）", "unknown": "待评估"}
    risk_hits = risk.get("rule_hits", [])

    return {
        "chief_complaint": raw_text or "未提供",
        "symptom_summary": symptom_text,
        "duration_days": duration,
        "patient_info": {
            "age": patient.get("age"),
            "gender": patient.get("gender"),
            "pregnancy_status": patient.get("pregnancy_status"),
        },
        "key_findings": findings,
        "allergy_history": {
            "has_allergy": allergy.get("has_allergy") if isinstance(allergy, dict) else None,
            "detail": allergy.get("detail") if isinstance(allergy, dict) else None,
        },
        "medication_history": {
            "has_used_medicine": medication.get("has_used_medicine") if isinstance(medication, dict) else None,
            "detail": medication.get("detail") if isinstance(medication, dict) else None,
        },
        "risk_level": risk_level,
        "risk_label": risk_labels.get(risk_level, risk_level),
        "risk_reasons": [h.get("reason", "") for h in risk_hits] if isinstance(risk_hits, list) else [],
        "dialogue_turns": dialogue.get("turn_count", 0),
        "generation_method": "template_fallback",
    }


def _system_prompt() -> str:
    from ai_preconsult_backend.app.configs.prompts import summary_system
    return summary_system()


def _user_prompt(state: dict[str, Any]) -> str:
    from ai_preconsult_backend.app.configs.prompts import summary_user
    chief = state.get("chief_complaint", {})
    slots = state.get("slots", {})
    patient = state.get("patient_basic_info", {})
    risk = state.get("risk", {})
    dialogue = state.get("dialogue", {})

    collected = json.dumps({
        "主诉": chief,
        "患者信息": patient,
        "症状与体征": slots,
        "风险评估": {
            "等级": risk.get("current_level"),
            "命中规则": [h.get("reason", "") for h in risk.get("rule_hits", [])] if isinstance(risk.get("rule_hits"), list) else [],
        },
        "对话轮次": dialogue.get("turn_count"),
        "仍缺失的关键字段": dialogue.get("missing_required_slots", []),
    }, ensure_ascii=False, indent=2)
    return summary_user(collected)


def _parse_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise LLMSummaryError("LLM did not return a JSON object")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise LLMSummaryError("LLM JSON is not an object")
    return parsed
