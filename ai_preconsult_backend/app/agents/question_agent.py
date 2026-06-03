from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class LLMQuestionError(RuntimeError):
    pass


def generate_natural_question(
    state: dict[str, Any],
    missing_slots: list[str],
    path_id: str,
    timeout_seconds: float | None = None,
) -> dict[str, Any] | None:
    """Let DeepSeek decide the most natural next question based on all remaining slots.

    Unlike generate_question() which is told exactly which slot to ask about,
    this function gives the LLM the full picture and lets it choose what to ask.
    """
    base_url = os.getenv("PRECONSULT_LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    model = os.getenv("PRECONSULT_LLM_MODEL", "deepseek-chat").strip()
    api_key = os.getenv("PRECONSULT_LLM_API_KEY") or "".strip()
    timeout = timeout_seconds or float(os.getenv("PRECONSULT_LLM_TIMEOUT", "20"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _natural_system_prompt()},
            {"role": "user", "content": _natural_user_prompt(state, missing_slots, path_id)},
        ],
        "temperature": 0.4,
        "max_tokens": 300,
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
        raise LLMQuestionError(f"LLM request failed: {exc}") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMQuestionError("LLM response shape is invalid") from exc

    return _parse_json_object(content)


def generate_question(
    state: dict[str, Any],
    question_key: str,
    timeout_seconds: float | None = None,
) -> dict[str, Any] | None:
    """Generate a context-aware follow-up question using DeepSeek.

    Returns a dict with 'question' and 'quick_replies', or None if the LLM
    should not handle this question_key.
    """
    base_url = os.getenv("PRECONSULT_LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
    model = os.getenv("PRECONSULT_LLM_MODEL", "deepseek-chat").strip()
    api_key = os.getenv("PRECONSULT_LLM_API_KEY") or "".strip()
    timeout = timeout_seconds or float(os.getenv("PRECONSULT_LLM_TIMEOUT", "20"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(state, question_key)},
        ],
        "temperature": 0.3,
        "max_tokens": 200,
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
        raise LLMQuestionError(f"LLM request failed: {exc}") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMQuestionError("LLM response shape is invalid") from exc

    return _parse_json_object(content)


SLOT_DESCRIPTIONS: dict[str, str] = {
    "patient_basic_info.age": "患者年龄",
    "patient_basic_info.gender": "患者性别",
    "slots.fever.duration_days": "发热持续天数",
    "slots.fever.max_temperature_c": "最高体温（摄氏度）",
    "slots.fever.current_temperature_c": "当前体温（摄氏度）",
    "slots.cough.cough_type": "咳嗽类型（干咳/有痰/无）及痰的颜色性状",
    "slots.cough.sputum": "痰的颜色（黄色/白色/绿色/血丝）",
    "slots.abdominal_pain.location": "腹痛位置（上腹/下腹/脐周/右下腹等）",
    "slots.abdominal_pain.pain_type": "腹痛性质（绞痛/钝痛/刺痛/胀痛）",
    "slots.abdominal_pain.severity": "腹痛程度（轻度/中度/重度）",
    "slots.abdominal_pain.duration_hours": "腹痛持续时间（小时）",
    "slots.abdominal_pain.radiation": "疼痛是否放射到其他部位（后背/肩膀等）",
    "slots.abdominal_pain.eating_relationship": "腹痛与进食的关系（餐前/餐后/无关）",
    "slots.headache.onset_speed": "头痛起病速度（sudden=突然/几秒到几分钟达峰，gradual=逐渐加重）",
    "slots.headache.location": "头痛部位（unilateral=单侧，bilateral=双侧，frontal=前额，temporal=太阳穴，occipital=后枕部，periorbital=眼眶周围，vertex=头顶，diffuse=全头）",
    "slots.headache.pain_type": "头痛性质（pulsating=搏动样跳痛，pressing=压迫样/紧箍感，stabbing=针刺样，electric=电击样，distension=胀痛）",
    "slots.headache.severity": "头痛程度（mild=轻度，moderate=中度，severe=重度/一生中最严重的头痛）",
    "slots.headache.duration_hours": "每次头痛持续小时数",
    "slots.headache.frequency": "发作频率（daily=每天，weekly=每周，monthly=每月，first_time=第一次）",
    "slots.headache.red_flags.thunderclap_onset": "是否突然发生、几秒到几分钟达到最痛（雷击样头痛）",
    "slots.headache.red_flags.neuro_symptoms": "是否有一侧肢体无力/麻木、说话不清、复视、视野缺损",
    "slots.headache.red_flags.fever_stiff_neck": "是否有发热、颈部僵硬、意识改变",
    "slots.headache.red_flags.trauma_anticoag": "近期是否有头部外伤或正在服用抗凝药",
    "slots.headache.red_flags.new_onset_over_50": "是否 50 岁以后新发的头痛",
    "slots.headache.red_flags.worsening_pattern": "头痛是否越来越重、越来越频繁",
    "slots.headache.red_flags.pregnancy_related": "是否怀孕或产后新发头痛",
    "slots.headache.red_flags.eye_symptoms": "是否有红眼、眼痛、看灯有彩虹圈",
    "slots.associated_symptoms.sore_throat": "是否有咽痛",
    "slots.associated_symptoms.fatigue": "是否有乏力",
    "slots.associated_symptoms.headache": "是否有头痛",
    "slots.associated_symptoms.diarrhea": "是否有腹泻",
    "slots.associated_symptoms.rash": "是否有皮疹",
    "slots.associated_symptoms.nausea_vomiting": "是否有恶心或呕吐",
    "slots.associated_symptoms.constipation": "是否有便秘",
    "slots.associated_symptoms.fever": "是否伴有发热",
    "slots.associated_symptoms.photophobia": "是否怕光",
    "slots.associated_symptoms.visual_aura": "是否有视物闪光、暗点等视觉先兆",
    "slots.associated_symptoms.neck_pain": "是否有颈肩痛",
    "slots.red_flags.shortness_of_breath": "是否有呼吸困难或憋气",
    "slots.red_flags.chest_pain": "是否有胸痛或胸闷",
    "slots.red_flags.hemoptysis": "是否有咳血或痰中带血",
    "slots.red_flags.confusion": "是否有意识模糊",
    "slots.red_flags.seizure": "是否有抽搐",
    "slots.red_flags.cyanosis": "是否有嘴唇或面色发紫",
    "slots.red_flags.peritoneal_signs": "是否有腹膜刺激征（腹部发硬、反跳痛）",
    "slots.red_flags.hematemesis": "是否有呕血或吐咖啡色物",
    "slots.red_flags.melena": "是否有黑便或便血",
    "slots.red_flags.syncope": "是否有晕厥或眼前发黑",
    "slots.allergy_history.has_allergy": "是否有药物或食物过敏史",
    "slots.allergy_history.detail": "过敏详情",
    "slots.medication_history.has_used_medicine": "是否已使用过药物",
    "slots.medication_history.detail": "已用药详情（药名、剂量、效果）",
    "red_flag_respiratory_group": "是否有呼吸困难、胸痛或咳血等呼吸系统红旗信号",
}


def _system_prompt() -> str:
    from ai_preconsult_backend.app.configs.prompts import question_system
    return question_system(json.dumps(SLOT_DESCRIPTIONS, ensure_ascii=False, indent=2))


def _user_prompt(state: dict[str, Any], question_key: str) -> str:
    chief = state.get("chief_complaint", {})
    slots = state.get("slots", {})
    patient = state.get("patient_basic_info", {})
    dialogue = state.get("dialogue", {})

    already_known: dict[str, Any] = {}
    if chief.get("main_symptoms"):
        already_known["已报告症状"] = chief["main_symptoms"]
    if chief.get("duration_days") is not None:
        already_known["病程天数"] = chief["duration_days"]
    if patient.get("age") is not None:
        already_known["年龄"] = patient["age"]
    if patient.get("gender"):
        already_known["性别"] = patient["gender"]

    fever = slots.get("fever", {})
    if isinstance(fever, dict):
        if fever.get("max_temperature_c") is not None:
            already_known["最高体温"] = f"{fever['max_temperature_c']}°C"
        if fever.get("duration_days") is not None:
            already_known["发热天数"] = fever["duration_days"]

    cough = slots.get("cough", {})
    if isinstance(cough, dict) and cough.get("has_cough") is not None:
        already_known["咳嗽情况"] = f"has_cough={cough['has_cough']}, type={cough.get('cough_type')}, sputum={cough.get('sputum')}"

    abdominal = slots.get("abdominal_pain", {})
    if isinstance(abdominal, dict):
        known_ab = {k: v for k, v in abdominal.items() if v is not None}
        if known_ab:
            already_known["腹痛情况"] = known_ab

    red_flags = slots.get("red_flags", {})
    if isinstance(red_flags, dict):
        known_rf = {k: v for k, v in red_flags.items() if v is not None}
        if known_rf:
            already_known["已确认的红旗信号"] = known_rf

    allergy = slots.get("allergy_history", {})
    if isinstance(allergy, dict) and allergy.get("has_allergy") is not None:
        already_known["过敏史"] = allergy

    medication = slots.get("medication_history", {})
    if isinstance(medication, dict) and medication.get("has_used_medicine") is not None:
        already_known["用药史"] = medication

    slot_desc = SLOT_DESCRIPTIONS.get(question_key, question_key)
    context = json.dumps({
        "当前待采集字段": f"{question_key}（{slot_desc}）",
        "已采集到的信息": already_known,
        "当前对话轮次": dialogue.get("turn_count", 0),
        "最大轮次": dialogue.get("max_turns", 5),
        "仍缺失字段": dialogue.get("missing_required_slots", []),
    }, ensure_ascii=False, indent=2)
    from ai_preconsult_backend.app.configs.prompts import question_user
    return question_user(context)


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
            raise LLMQuestionError("LLM did not return a JSON object")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise LLMQuestionError("LLM JSON is not an object")
    return parsed


PATH_LABELS: dict[str, str] = {
    "fever_cough_v1": "发热/咳嗽/咽痛",
    "abdominal_pain_v1": "腹痛",
    "headache_v1": "头痛",
}


def _natural_system_prompt() -> str:
    return (
        "你是医院预问诊系统的智能追问护士。根据已采集的患者信息，"
        "自然地与患者交流，引导患者补充还缺失的信息。\n"
        "\n"
        "追问规则：\n"
        "- 应该优先追问列表中的第一个字段，它是最需要采集的。\n"
        "- 不要反复追问同一个问题。如果患者描述已暗示了答案，就视为已采集。\n"
        "  例：患者说'慢慢加重的'→已表明不是突然发作，不要再追问。\n"
        "- 一次只问1个问题，不要一次问太多。\n"
        "- 语气温和、专业、自然，像真人护士在问诊。\n"
        "- 引用患者之前提到的信息。\n"
        "- 不要诊断，不要推荐药物，不要给治疗方案。\n"
        "- 只输出一个 JSON 对象，不要输出 Markdown，不要解释。\n"
        "\n"
        """输出格式: {"question": "...", "quick_replies": [...]}\n"""
        "- question: 自然流畅的追问。\n"
        "- quick_replies: 2-3个快捷回复，帮助患者快速作答。\n"
    )


def _natural_user_prompt(state: dict[str, Any], missing_slots: list[str], path_id: str) -> str:
    path_label = PATH_LABELS.get(path_id, path_id)
    chief = state.get("chief_complaint", {})
    slots = state.get("slots", {})
    patient = state.get("patient_basic_info", {})

    collected_parts: list[str] = []
    if chief.get("main_symptoms"):
        collected_parts.append(f"主诉：{'、'.join(chief['main_symptoms'])}")
    if patient.get("age") is not None:
        collected_parts.append(f"年龄：{patient['age']}岁")
    if patient.get("gender"):
        collected_parts.append(f"性别：{patient['gender']}")
    if patient.get("pregnancy_status") is True:
        collected_parts.append("已确认怀孕")
    elif patient.get("pregnancy_status") is False:
        collected_parts.append("未怀孕")

    fever = slots.get("fever", {})
    if isinstance(fever, dict):
        if fever.get("max_temperature_c") is not None:
            collected_parts.append(f"最高体温：{fever['max_temperature_c']}°C")
        if fever.get("duration_days") is not None:
            collected_parts.append(f"发热持续：{fever['duration_days']}天")

    cough = slots.get("cough", {})
    if isinstance(cough, dict):
        if cough.get("has_cough") is True:
            collected_parts.append(f"有咳嗽（{cough.get('cough_type', '未知')}）")
        elif cough.get("has_cough") is False:
            collected_parts.append("无咳嗽")

    ab = slots.get("abdominal_pain", {})
    if isinstance(ab, dict):
        parts = []
        for k, v in ab.items():
            if v is not None:
                parts.append(f"{k}={v}")
        if parts:
            collected_parts.append(f"腹痛：{', '.join(parts)}")

    headache = slots.get("headache", {})
    if isinstance(headache, dict):
        parts = []
        for k, v in headache.items():
            if k == "red_flags":
                if isinstance(v, dict):
                    rf_parts = [f"{rk}={rv}" for rk, rv in v.items() if rv is not None]
                    if rf_parts:
                        parts.append(f"红旗：{', '.join(rf_parts)}")
            elif v is not None:
                parts.append(f"{k}={v}")
        if parts:
            collected_parts.append(f"头痛：{', '.join(parts)}")

    assoc = slots.get("associated_symptoms", {})
    if isinstance(assoc, dict):
        positives = [k for k, v in assoc.items() if v is True]
        if positives:
            collected_parts.append(f"伴随症状：{'、'.join(positives)}")

    rf = slots.get("red_flags", {})
    if isinstance(rf, dict):
        confirmed = [(k, v) for k, v in rf.items() if v is not None]
        if confirmed:
            rf_parts = [f"{k}={'是' if v else '否'}" for k, v in confirmed]
            collected_parts.append(f"红旗信号：{'; '.join(rf_parts)}")

    allergy = slots.get("allergy_history", {})
    if isinstance(allergy, dict) and allergy.get("has_allergy") is not None:
        collected_parts.append(f"过敏史：{'有' if allergy['has_allergy'] else '无'}")

    med = slots.get("medication_history", {})
    if isinstance(med, dict) and med.get("has_used_medicine") is not None:
        collected_parts.append(f"用药史：{'有' if med['has_used_medicine'] else '无'}")

    missing_labels = [SLOT_DESCRIPTIONS.get(s, s) for s in missing_slots]

    context = json.dumps({
        "预问诊路径": path_label,
        "已采集到的信息": collected_parts,
        "优先追问": missing_labels[0] if missing_labels else "无",
        "还需采集的字段": missing_labels,
    }, ensure_ascii=False, indent=2)
    return f"请根据'优先追问'字段生成自然的问题：\n{context}\n"
