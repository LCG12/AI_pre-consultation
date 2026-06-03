from __future__ import annotations

from uuid import uuid4

from ai_preconsult_backend.app.agents.extraction_agent import LLMExtractionError, extract_slots_with_llm
from ai_preconsult_backend.app.agents.question_agent import LLMQuestionError, generate_natural_question, generate_question
from ai_preconsult_backend.app.core.config_loader import get_path_config, get_patient_report_templates
from ai_preconsult_backend.app.engines.risk_engine import evaluate_risk
from ai_preconsult_backend.app.engines.triage_engine import recommend_departments
from ai_preconsult_backend.app.models.schemas import (
    PreconsultResponse,
    PreconsultState,
    RobotContext,
)
from ai_preconsult_backend.app.tools.dictionary_tool import (
    detect_red_flags,
    detect_safety_issue,
    extract_by_dictionary,
)
from ai_preconsult_backend.app.tools.slot_tool import missing_required_slots, plan_next_question
from ai_preconsult_backend.app.tools.state_tool import get_by_path, set_by_path
from ai_preconsult_backend.app.tools.template_tool import (
    build_emergency_reply,
    build_patient_report,
    build_question,
)

GREETING_PATTERNS = ["你是谁", "你叫什么", "你是机器人", "你是AI", "你好", "您好", "嗨", "在吗", "能做什么", "干什么的", "你会什么", "介绍一下"]
GREETING_REPLY = "您好，我是AI预问诊助手，帮您在就诊前整理症状信息。请告诉我您哪里不舒服，比如哪里疼、疼了多久、有什么感觉？"


AVAILABLE_PATHS = {
    "fever_cough_v1": {"name": "发热/咳嗽/咽痛", "opening": "请问您哪里不舒服？比如发烧、咳嗽或者喉咙痛？"},
    "abdominal_pain_v1": {"name": "腹痛", "opening": "您说肚子不舒服，具体是哪个位置疼？疼了多久了？是什么样的疼法？"},
    "headache_v1": {"name": "头痛", "opening": "您说头痛，具体是哪个位置疼？是一侧还是两侧？是什么样的痛感？疼了多久了？"},
}


def create_initial_state(source: str = "robot", robot_id: str | None = None, location: str | None = None, path_id: str | None = None, age: int | None = None, gender: str | None = None) -> PreconsultState:
    session_id = f"s_{uuid4().hex[:12]}"
    effective_path = path_id if path_id and path_id in AVAILABLE_PATHS else "fever_cough_v1"
    path_config = get_path_config(effective_path)
    return PreconsultState(
        session_id=session_id,
        source=source,
        robot_context=RobotContext(robot_id=robot_id, location=location),
        path_id=path_config["path_id"],
        patient_basic_info={"age": age, "gender": gender},
        dialogue={"max_turns": path_config["max_turns"]},
    )


def create_session_response(state: PreconsultState) -> PreconsultResponse:
    path_info = AVAILABLE_PATHS.get(state.path_id, {})
    reply = path_info.get("opening", "请问您哪里不舒服？")
    return PreconsultResponse(
        session_id=state.session_id,
        status="created",
        reply=reply,
        display_text=reply,
        risk_level="unknown",
    )


def handle_message(state: PreconsultState, text: str, asr_confidence: float | None = None) -> tuple[PreconsultState, PreconsultResponse, dict]:
    state_dict = state.model_dump()
    state_dict["status"] = "in_progress"
    state_dict["dialogue"]["turn_count"] += 1

    audit: dict = {
        "extracted_slots": {},
        "red_flag_precheck": {},
        "safety_blocked": False,
        "extraction_source": "none",
        "llm_error": None,
        "uncertain_fields": [],
        "raw_evidence": [],
    }

    if asr_confidence is not None and asr_confidence < 0.6:
        reply = "我刚才没有完全听清。请您再说一遍主要哪里不舒服，或者选择屏幕上的选项。"
        response = PreconsultResponse(
            session_id=state.session_id,
            status="in_progress",
            reply=reply,
            display_text=reply,
            quick_replies=["重新说明", "不确定"],
            risk_level=state.risk.current_level,
        )
        return PreconsultState.model_validate(state_dict), response, audit

    if _is_greeting(text) and not state.chief_complaint.main_symptoms:
        state_dict["dialogue"]["last_question_key"] = "_greeting"
        reply = GREETING_REPLY
        response = PreconsultResponse(
            session_id=state.session_id,
            status="in_progress",
            reply=reply,
            display_text=reply,
            quick_replies=["肚子疼", "发烧", "咳嗽"],
            risk_level=state.risk.current_level,
        )
        return PreconsultState.model_validate(state_dict), response, audit

    if state.dialogue.pending_confirmation:
        confirmed = _handle_confirmation_response(text, state_dict, audit)
        state_dict["dialogue"]["pending_confirmation"] = None
        if confirmed:
            audit["extraction_source"] = "confirmation"
            confirmation_handled = True
        else:
            confirmation_handled = False
    else:
        confirmation_handled = False

    if detect_safety_issue(text):
        audit["safety_blocked"] = True

    red_hits = detect_red_flags(text)
    audit["red_flag_precheck"] = red_hits
    for field, value in red_hits.items():
        set_by_path(state_dict, f"slots.red_flags.{field}", value)

    precheck_level, precheck_hits, precheck_should_stop = evaluate_risk(state_dict)
    if precheck_level == "red" and precheck_should_stop:
        state_dict["risk"]["current_level"] = precheck_level
        state_dict["risk"]["rule_hits"] = [hit.model_dump() for hit in precheck_hits]
        departments, _department_reasons = recommend_departments(state_dict)
        risk_reasons = [hit.reason for hit in precheck_hits]
        reply = build_emergency_reply(risk_reasons)
        state_dict["status"] = "emergency"
        new_state = PreconsultState.model_validate(state_dict)
        return new_state, PreconsultResponse(
            session_id=state.session_id,
            status="emergency",
            reply=reply,
            display_text=reply,
            risk_level="red",
            risk_reasons=risk_reasons,
            recommended_action="立即联系现场医护或前往急诊",
            recommended_departments=departments,
            should_stop_dialogue=True,
            doctor_summary_status="generating",
        ), audit

    if not confirmation_handled:
        extracted: dict = {}
        try:
            llm_result = extract_slots_with_llm(text, state_dict)
            extracted = llm_result["extracted_slots"]
            audit["extraction_source"] = "llm"
            audit["uncertain_fields"] = llm_result["uncertain_fields"]
            audit["raw_evidence"] = llm_result["raw_evidence"]
        except LLMExtractionError as exc:
            extracted = extract_by_dictionary(text)
            audit["extraction_source"] = "dictionary_fallback"
            audit["llm_error"] = str(exc)

        audit["extracted_slots"] = extracted
        for path, value in extracted.items():
            if path.startswith("_"):
                continue
            if path == "chief_complaint.raw_text" and state_dict["chief_complaint"].get("raw_text"):
                continue
            if path == "chief_complaint.duration_days" and state_dict["chief_complaint"].get("duration_days") is not None:
                continue
            if path == "chief_complaint.main_symptoms":
                existing = state_dict["chief_complaint"].get("main_symptoms", [])
                if not value and existing:
                    continue
                merged = list(dict.fromkeys(existing + value))
                set_by_path(state_dict, path, merged)
            else:
                set_by_path(state_dict, path, value)

    detected_path = _detect_path(state_dict)
    if detected_path and detected_path != state_dict["path_id"]:
        try:
            path_config = get_path_config(detected_path)
            state_dict["path_id"] = detected_path
            state_dict["dialogue"]["max_turns"] = path_config["max_turns"]
            state_dict["dialogue"]["skipped_slots"] = []
        except Exception:
            pass

    risk_level, rule_hits, should_stop = evaluate_risk(state_dict)
    state_dict["risk"]["current_level"] = risk_level
    state_dict["risk"]["rule_hits"] = [hit.model_dump() for hit in rule_hits]

    departments, _department_reasons = recommend_departments(state_dict)
    risk_reasons = [hit.reason for hit in rule_hits]

    if risk_level == "red" and should_stop:
        reply = build_emergency_reply(risk_reasons)
        state_dict["status"] = "emergency"
        new_state = PreconsultState.model_validate(state_dict)
        return new_state, PreconsultResponse(
            session_id=state.session_id,
            status="emergency",
            reply=reply,
            display_text=reply,
            risk_level="red",
            risk_reasons=risk_reasons,
            recommended_action="立即联系现场医护或前往急诊",
            recommended_departments=departments,
            should_stop_dialogue=True,
            doctor_summary_status="generating",
        ), audit

    state_dict["dialogue"]["missing_required_slots"] = missing_required_slots(state_dict)

    if audit["safety_blocked"]:
        reply = get_patient_report_templates()["safety"]
        new_state = PreconsultState.model_validate(state_dict)
        return new_state, PreconsultResponse(
            session_id=state.session_id,
            status="in_progress",
            reply=reply,
            display_text=reply,
            quick_replies=[],
            risk_level=risk_level,
            risk_reasons=risk_reasons,
            recommended_departments=departments,
        ), audit

    uncertain_fields = audit.get("uncertain_fields", [])
    if uncertain_fields and not confirmation_handled:
        for field in uncertain_fields:
            value = get_by_path(state_dict, field)
            if value is not None:
                state_dict["dialogue"]["pending_confirmation"] = {"field": field, "value": value}
                reply, quick_replies = _build_confirmation_question(state_dict, field, value)
                state_dict["dialogue"]["last_question_key"] = f"_confirm_{field}"
                new_state = PreconsultState.model_validate(state_dict)
                return new_state, PreconsultResponse(
                    session_id=state.session_id,
                    status="in_progress",
                    reply=reply,
                    display_text=reply,
                    quick_replies=quick_replies,
                    risk_level=risk_level,
                    risk_reasons=risk_reasons,
                    recommended_departments=departments,
                ), audit

    next_question_key = plan_next_question(state_dict)
    if next_question_key:
        retries = state_dict["dialogue"].get("question_retries", {})
        prev_key = state.dialogue.last_question_key
        if next_question_key == prev_key:
            retries[next_question_key] = retries.get(next_question_key, 0) + 1
        else:
            retries.pop(next_question_key, None)
        state_dict["dialogue"]["question_retries"] = retries

        if retries.get(next_question_key, 0) >= 3:
            state_dict["dialogue"]["skipped_slots"].append(next_question_key)
            retries.pop(next_question_key, None)
            next_question_key = plan_next_question(state_dict)
        if next_question_key:
            state_dict["dialogue"]["last_question_key"] = next_question_key
            reply, quick_replies = _generate_question(state_dict, next_question_key)
            new_state = PreconsultState.model_validate(state_dict)
            return new_state, PreconsultResponse(
                session_id=state.session_id,
                status="in_progress",
                reply=reply,
                display_text=reply,
                quick_replies=quick_replies,
                risk_level=risk_level,
                risk_reasons=risk_reasons,
                recommended_departments=departments,
            ), audit

    patient_report = build_patient_report(risk_level, risk_reasons, departments)
    state_dict["status"] = "completed"
    new_state = PreconsultState.model_validate(state_dict)
    return new_state, PreconsultResponse(
        session_id=state.session_id,
        status="completed",
        reply=patient_report["message"],
        display_text=patient_report["message"],
        risk_level=risk_level,
        risk_reasons=risk_reasons,
        recommended_action="建议尽快线下就医" if risk_level == "yellow" else "普通门诊或继续观察",
        recommended_departments=departments,
        should_stop_dialogue=False,
        patient_report=patient_report,
        doctor_summary_status="generating",
    ), audit


BASIC_INFO_KEYS = {"patient_basic_info.age", "patient_basic_info.gender", "patient_basic_info.pregnancy_status"}


def _generate_question(state_dict: dict, question_key: str) -> tuple[str, list[str]]:
    """Generate a question: LLM natural conversation first, then old per-slot LLM, then static template."""
    missing = state_dict["dialogue"].get("missing_required_slots", [])
    skipped = state_dict["dialogue"].get("skipped_slots", [])
    missing = [s for s in missing if s not in skipped]
    path_id = state_dict.get("path_id", "fever_cough_v1")

    if missing and question_key not in BASIC_INFO_KEYS:
        try:
            result = generate_natural_question(state_dict, missing, path_id)
            if result and result.get("question"):
                qr = result.get("quick_replies")
                if isinstance(qr, list) and qr:
                    return result["question"], qr
                return result["question"], []
        except LLMQuestionError:
            pass

    try:
        result = generate_question(state_dict, question_key)
        if result and result.get("question"):
            quick_replies = result.get("quick_replies")
            if isinstance(quick_replies, list) and quick_replies:
                return result["question"], quick_replies
            return result["question"], []
    except LLMQuestionError:
        pass
    return build_question(question_key)


CONFIRMATION_LABELS: dict[str, str] = {
    "patient_basic_info.age": "年龄 {value} 岁",
    "slots.fever.duration_days": "发热持续 {value} 天",
    "slots.fever.max_temperature_c": "最高体温 {value}",
    "slots.fever.current_temperature_c": "当前体温 {value}",
    "slots.cough.cough_type": "咳嗽类型是 {value}",
    "slots.cough.sputum": "痰的颜色是 {value}",
    "slots.abdominal_pain.location": "腹痛位置在 {value}",
    "slots.abdominal_pain.pain_type": "疼痛性质是 {value}",
    "slots.abdominal_pain.severity": "疼痛程度为 {value}",
    "slots.abdominal_pain.duration_hours": "腹痛持续 {value} 小时",
    "slots.abdominal_pain.radiation": "疼痛放射到 {value}",
    "slots.abdominal_pain.eating_relationship": "与进食关系为 {value}",
}
CONFIRM_POSITIVE = {"对", "是的", "没错", "嗯", "对的", "是", "确认", "正确"}

VALUE_LABELS: dict[str, str] = {
    "dull": "钝痛", "colicky": "绞痛", "stabbing": "刺痛",
    "distension": "胀痛", "burning": "烧灼痛",
    "right_lower": "右下腹", "left_lower": "左下腹",
    "right_upper": "右上腹", "left_upper": "左上腹",
    "upper_abdomen": "上腹部", "lower_abdomen": "下腹部",
    "periumbilical": "脐周", "diffuse": "全腹",
    "mild": "轻度", "moderate": "中度", "severe": "重度",
    "sudden": "突发", "gradual": "逐渐",
    "dry": "干咳", "productive": "有痰",
    "before_meal": "餐前加重", "after_meal": "餐后加重", "unrelated": "与进食无关",
    "back": "后背", "shoulder": "肩膀", "none": "无",
}


def _build_confirmation_question(state_dict: dict, field: str, value: Any) -> tuple[str, list[str]]:
    """Generate a confirmation question from template."""
    label = CONFIRMATION_LABELS.get(field, field)
    raw = str(value)
    if raw in VALUE_LABELS:
        display = VALUE_LABELS[raw]
    elif field.endswith("_temperature_c"):
        display = f"{value}°C"
    else:
        display = raw
    question = f"您说的是{label.format(value=display)}，对吗？"
    return question, ["对", "不对", "不确定"]


def _handle_confirmation_response(text: str, state_dict: dict, audit: dict) -> bool:
    """Process patient response to a confirmation question.
    Returns True if the response was fully handled (confirmed or skipped).
    Returns False if the response should fall through to normal extraction.
    """
    pending = state_dict["dialogue"]["pending_confirmation"]
    if not pending:
        return True

    field = pending["field"]
    tentative_value = pending["value"]
    normalized = text.strip().replace("。", "").replace("，", "").replace(",", "")

    if normalized in CONFIRM_POSITIVE:
        audit["extracted_slots"] = {field: tentative_value}
        return True

    if normalized in {"不知道", "不确定", "说不清", "不清楚"}:
        state_dict["dialogue"]["skipped_slots"].append(field)
        return True

    # Not a direct confirm/deny — treat as normal answer, fall through to extraction
    return False


def _detect_path(state_dict: dict) -> str | None:
    symptoms = state_dict.get("chief_complaint", {}).get("main_symptoms", [])
    if "headache" in symptoms:
        return "headache_v1"
    if "abdominal_pain" in symptoms:
        return "abdominal_pain_v1"
    if any(s in symptoms for s in ("fever", "cough", "sore_throat")):
        return "fever_cough_v1"
    return None


def _is_greeting(text: str) -> bool:
    """Check if text is a greeting or off-topic question."""
    normalized = text.strip().replace("？", "").replace("?", "").replace("！", "").replace("!", "")
    for pattern in GREETING_PATTERNS:
        if pattern in normalized:
            return True
    return False
