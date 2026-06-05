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

    symptom_labels = {"fever": "发热", "cough": "咳嗽", "sore_throat": "咽痛", "headache": "头痛", "abdominal_pain": "腹痛"}
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

    ab = slots.get("abdominal_pain", {})
    if isinstance(ab, dict):
        loc_map = {"right_lower": "右下腹", "left_lower": "左下腹", "upper_abdomen": "上腹",
                   "lower_abdomen": "下腹", "periumbilical": "脐周", "diffuse": "全腹"}
        pain_map = {"colicky": "绞痛", "dull": "钝痛", "stabbing": "刺痛", "distension": "胀痛"}
        parts = []
        if ab.get("location"): parts.append(loc_map.get(ab["location"], ab["location"]))
        if ab.get("pain_type"): parts.append(pain_map.get(ab["pain_type"], ab["pain_type"]))
        if ab.get("severity"): parts.append(ab["severity"])
        if parts: findings.append(f"腹痛: {', '.join(parts)}")

    headache = slots.get("headache", {})
    if isinstance(headache, dict):
        loc_map = {"unilateral": "单侧", "bilateral": "双侧", "frontal": "前额", "temporal": "太阳穴",
                   "occipital": "后枕部", "diffuse": "全头"}
        pain_map = {"pulsating": "搏动样", "pressing": "压迫样", "stabbing": "针刺样",
                    "electric": "电击样", "distension": "胀痛"}
        sev_map = {"mild": "轻度", "moderate": "中度", "severe": "重度"}
        parts = []
        if headache.get("location"): parts.append(loc_map.get(headache["location"], headache["location"]))
        if headache.get("pain_type"): parts.append(pain_map.get(headache["pain_type"], headache["pain_type"]))
        if headache.get("severity"): parts.append(sev_map.get(headache["severity"], headache["severity"]))
        if headache.get("duration_hours"): parts.append(f"持续{headache['duration_hours']}")
        if parts: findings.append(f"头痛: {', '.join(parts)}")

    assoc = slots.get("associated_symptoms", {})
    if isinstance(assoc, dict):
        assoc_labels = {
            "sore_throat": "咽痛", "fatigue": "乏力", "headache": "头痛",
            "diarrhea": "腹泻", "rash": "皮疹", "nausea_vomiting": "恶心呕吐",
            "photophobia": "怕光", "visual_aura": "视觉先兆", "neck_pain": "颈肩痛",
            "fever": "伴发热",
        }
        positives = [label for key, label in assoc_labels.items() if assoc.get(key) is True]
        if positives: findings.append(f"伴随: {'、'.join(positives)}")

    red_flags = slots.get("red_flags", {})
    headache_rf = (headache.get("red_flags") if isinstance(headache, dict) else None) or {}
    all_rf = {**red_flags, **headache_rf}
    if isinstance(all_rf, dict):
        rf_labels = {
            "thunderclap_onset": "雷击样发作", "neuro_symptoms": "神经症状",
            "fever_stiff_neck": "发热/颈强直", "trauma_anticoag": "外伤/抗凝",
            "new_onset_over_50": "50岁后新发", "worsening_pattern": "进行性加重",
            "pregnancy_related": "妊娠相关", "eye_symptoms": "眼部症状",
            "shortness_of_breath": "呼吸困难", "chest_pain": "胸痛", "hemoptysis": "咳血",
            "peritoneal_signs": "腹膜刺激征", "hematemesis": "呕血", "melena": "黑便",
            "syncope": "晕厥",
        }
        positives = [rf_labels[k] for k, v in all_rf.items() if v is True and k in rf_labels]
        if positives: findings.append(f"红旗信号阳性: {'、'.join(positives)}")

    allergy = slots.get("allergy_history", {})
    medication = slots.get("medication_history", {})

    risk_level = risk.get("current_level", "unknown")
    risk_labels = {"red": "红旗（紧急）", "yellow": "黄旗（需关注）", "green": "绿旗（低风险）", "unknown": "待评估"}
    risk_hits = risk.get("rule_hits", [])
    uncertain_slots = _format_uncertain_slots(dialogue.get("uncertain_slots", []))

    return {
        "chief_complaint": raw_text or "未提供",
        "symptom_summary": symptom_text,
        "duration_days": duration,
        "patient_info": {"age": patient.get("age"), "gender": patient.get("gender"), "pregnancy_status": patient.get("pregnancy_status")},
        "key_findings": findings,
        "allergy_history": {"has_allergy": allergy.get("has_allergy") if isinstance(allergy, dict) else None, "detail": allergy.get("detail") if isinstance(allergy, dict) else None},
        "medication_history": {"has_used_medicine": medication.get("has_used_medicine") if isinstance(medication, dict) else None, "detail": medication.get("detail") if isinstance(medication, dict) else None},
        "risk_level": risk_level,
        "risk_label": risk_labels.get(risk_level, risk_level),
        "risk_reasons": [h.get("reason", "") for h in risk_hits] if isinstance(risk_hits, list) else [],
        "information_gaps": [m for m in dialogue.get("missing_required_slots", []) if isinstance(m, str)],
        "patient_uncertain": uncertain_slots,
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
        "患者明确表示不确定的字段": _format_uncertain_slots(dialogue.get("uncertain_slots", [])),
    }, ensure_ascii=False, indent=2)
    return summary_user(collected)


def _format_uncertain_slots(slots: Any) -> list[str]:
    if not isinstance(slots, list):
        return []
    return [_slot_label(slot) for slot in slots if isinstance(slot, str)]


def _slot_label(slot: str) -> str:
    labels = {
        "patient_basic_info.age": "年龄",
        "patient_basic_info.gender": "性别",
        "patient_basic_info.pregnancy_status": "是否怀孕/产后",
        "slots.headache.onset_speed": "头痛起病速度",
        "slots.headache.location": "头痛部位",
        "slots.headache.pain_type": "头痛性质",
        "slots.headache.severity": "头痛程度",
        "slots.headache.duration_hours": "头痛持续时间",
        "slots.headache.frequency": "头痛频率",
        "slots.headache.red_flags.thunderclap_onset": "雷击样头痛",
        "slots.headache.red_flags.neuro_symptoms": "神经症状",
        "slots.headache.red_flags.fever_stiff_neck": "发热/颈强直/意识改变",
        "slots.headache.red_flags.trauma_anticoag": "头外伤或抗凝药",
        "slots.headache.red_flags.new_onset_over_50": "50岁后新发头痛",
        "slots.headache.red_flags.worsening_pattern": "头痛进行性加重",
        "slots.headache.red_flags.pregnancy_related": "妊娠相关头痛",
        "slots.headache.red_flags.eye_symptoms": "眼部症状",
        "slots.red_flags.shortness_of_breath": "呼吸困难",
        "slots.red_flags.chest_pain": "胸痛",
        "slots.red_flags.hemoptysis": "咳血",
        "slots.red_flags.peritoneal_signs": "腹膜刺激征",
        "slots.red_flags.hematemesis": "呕血",
        "slots.red_flags.melena": "黑便/便血",
        "slots.red_flags.syncope": "晕厥",
        "slots.associated_symptoms.nausea_vomiting": "恶心呕吐",
        "slots.associated_symptoms.photophobia": "怕光",
        "slots.associated_symptoms.visual_aura": "视觉先兆",
        "slots.associated_symptoms.neck_pain": "颈肩痛",
        "slots.medication_history.has_used_medicine": "是否用药",
        "slots.medication_history.detail": "用药详情",
        "slots.allergy_history.has_allergy": "是否过敏",
        "slots.allergy_history.detail": "过敏详情",
    }
    return labels.get(slot, slot)


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
