from ai_preconsult_backend.app.services.preconsult_service import create_initial_state, handle_message
from ai_preconsult_backend.app.engines.risk_engine import evaluate_risk


def test_red_flag_chest_pain_and_dyspnea_stops_dialogue():
    state = create_initial_state()

    new_state, response, audit = handle_message(state, "胸口疼，喘不上气", 0.95)

    assert response.status == "emergency"
    assert response.risk_level == "red"
    assert response.should_stop_dialogue is True
    assert response.recommended_departments == ["急诊"]
    assert audit["red_flag_precheck"]["chest_pain"] is True
    assert audit["red_flag_precheck"]["shortness_of_breath"] is True
    assert new_state.status == "emergency"


def test_yellow_fever_three_days():
    state = create_initial_state()

    _new_state, response, audit = handle_message(state, "我发烧三天，最高38度8，没有胸痛，也没有喘", 0.95)

    assert response.risk_level == "yellow"
    assert "发热持续3天及以上" in response.risk_reasons
    assert audit["extracted_slots"]["slots.fever.duration_days"] == 3
    assert audit["extracted_slots"]["slots.fever.max_temperature_c"] == 38.8


def test_low_asr_confidence_asks_repeat():
    state = create_initial_state()

    _new_state, response, _audit = handle_message(state, "发烧", 0.3)

    assert response.status == "in_progress"
    assert "没有完全听清" in response.reply


def test_safety_question_is_blocked():
    state = create_initial_state()

    _new_state, response, audit = handle_message(state, "我是不是肺炎，吃什么药", 0.95)

    assert audit["safety_blocked"] is True
    assert "不能为您做诊断或提供处方建议" in response.reply


def test_llm_extraction_is_used_when_available(monkeypatch):
    state = create_initial_state()

    def fake_extract_slots_with_llm(text, state_dict):
        return {
            "extracted_slots": {
                "chief_complaint.raw_text": text,
                "chief_complaint.main_symptoms": ["fever"],
                "slots.fever.duration_days": 4,
                "slots.fever.max_temperature_c": 38.5,
                "slots.red_flags.chest_pain": False,
            },
            "uncertain_fields": [],
            "raw_evidence": [{"field": "slots.fever.duration_days", "text": "四天"}],
        }

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        fake_extract_slots_with_llm,
    )

    new_state, response, audit = handle_message(state, "发热四天，最高38度5，没有胸痛", 0.95)

    assert audit["extraction_source"] == "llm"
    assert new_state.slots.fever.duration_days == 4
    assert new_state.slots.fever.max_temperature_c == 38.5
    assert response.risk_level == "yellow"


def test_dictionary_fallback_when_llm_fails(monkeypatch):
    from ai_preconsult_backend.app.agents.extraction_agent import LLMExtractionError

    state = create_initial_state()

    def fake_extract_slots_with_llm(text, state_dict):
        raise LLMExtractionError("timeout")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        fake_extract_slots_with_llm,
    )

    new_state, response, audit = handle_message(state, "我发烧三天，最高38度8，没有胸痛，也没有喘", 0.95)

    assert audit["extraction_source"] == "dictionary_fallback"
    assert "timeout" in audit["llm_error"]
    assert new_state.slots.fever.duration_days == 3
    assert response.risk_level == "yellow"


def test_short_negative_answer_uses_previous_red_flag_question(monkeypatch):
    state = create_initial_state()

    def first_extract(text, state_dict):
        return {
            "extracted_slots": {
                "chief_complaint.raw_text": text,
                "chief_complaint.main_symptoms": ["fever"],
                "slots.fever.duration_days": 3,
                "slots.fever.max_temperature_c": 38.8,
                "slots.red_flags.chest_pain": False,
                "slots.red_flags.shortness_of_breath": False,
            },
            "uncertain_fields": [],
            "raw_evidence": [],
        }

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        first_extract,
    )

    state, first_response, _first_audit = handle_message(state, "我发烧三天，最高38度8，没有胸痛，也没有喘。", 0.95)
    assert first_response.reply == "目前有没有呼吸困难、胸痛或咳血？"
    assert state.dialogue.last_question_key == "red_flag_respiratory_group"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("short contextual answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    state, second_response, second_audit = handle_message(state, "没有", 0.95)

    assert second_audit["extraction_source"] == "contextual_rule"
    assert state.slots.red_flags.shortness_of_breath is False
    assert state.slots.red_flags.chest_pain is False
    assert state.slots.red_flags.hemoptysis is False
    assert state.chief_complaint.raw_text == "我发烧三天，最高38度8，没有胸痛，也没有喘。"
    assert second_response.reply != "目前有没有呼吸困难、胸痛或咳血？"


def test_sputum_color_answer_uses_previous_cough_question(monkeypatch):
    state = create_initial_state()
    state.status = "in_progress"
    state.chief_complaint.raw_text = "我发烧三天，最高38度8，没有胸痛，也没有喘。"
    state.chief_complaint.main_symptoms = ["fever"]
    state.slots.fever.duration_days = 3
    state.slots.fever.max_temperature_c = 38.8
    state.slots.red_flags.shortness_of_breath = False
    state.slots.red_flags.chest_pain = False
    state.slots.red_flags.hemoptysis = False
    state.patient_basic_info.age = 25
    state.dialogue.turn_count = 3
    state.dialogue.last_question_key = "slots.cough.cough_type"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("cough contextual answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    new_state, response, audit = handle_message(state, "黄色", 0.95)

    assert audit["extraction_source"] == "contextual_rule"
    assert new_state.slots.cough.has_cough is True
    assert new_state.slots.cough.cough_type == "productive"
    assert new_state.slots.cough.sputum == "yellow"
    assert response.reply != "咳嗽是干咳还是有痰？如果有痰，痰是什么颜色？"


def test_headache_text_duration_does_not_crash_and_hits_yellow():
    state = create_initial_state(path_id="headache_v1").model_dump()
    state["chief_complaint"]["main_symptoms"] = ["headache"]
    state["slots"]["headache"]["duration_hours"] = "80小时"

    level, hits, _should_stop = evaluate_risk(state)

    assert level == "yellow"
    assert any(hit.rule_id == "YELLOW_HEADACHE_LONG" for hit in hits)


def test_abdominal_text_duration_days_hits_yellow():
    state = create_initial_state(path_id="abdominal_pain_v1").model_dump()
    state["chief_complaint"]["main_symptoms"] = ["abdominal_pain"]
    state["slots"]["abdominal_pain"]["duration_hours"] = "两天"

    level, hits, _should_stop = evaluate_risk(state)

    assert level == "yellow"
    assert any(hit.rule_id == "YELLOW_ABDO_LONG" for hit in hits)


def test_uncertain_answer_skips_current_headache_slot(monkeypatch):
    state = create_initial_state(path_id="headache_v1")
    state.status = "in_progress"
    state.chief_complaint.main_symptoms = ["headache"]
    state.patient_basic_info.age = 30
    state.patient_basic_info.gender = "male"
    state.slots.headache.red_flags.thunderclap_onset = False
    state.slots.headache.red_flags.neuro_symptoms = False
    state.slots.headache.red_flags.fever_stiff_neck = False
    state.slots.headache.red_flags.trauma_anticoag = False
    state.slots.headache.red_flags.new_onset_over_50 = False
    state.slots.headache.red_flags.worsening_pattern = False
    state.slots.headache.red_flags.pregnancy_related = False
    state.slots.headache.red_flags.eye_symptoms = False
    state.dialogue.last_question_key = "slots.headache.onset_speed"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("uncertain contextual answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    new_state, response, audit = handle_message(state, "不确定", 0.95)

    assert audit["extraction_source"] == "contextual_rule"
    assert "slots.headache.onset_speed" in new_state.dialogue.uncertain_slots
    assert response.reply != "头痛是突然一下就很痛，还是慢慢加重的？"


def test_uncertain_thunderclap_also_skips_onset_speed(monkeypatch):
    state = create_initial_state(path_id="headache_v1")
    state.status = "in_progress"
    state.chief_complaint.main_symptoms = ["headache"]
    state.patient_basic_info.age = 99
    state.patient_basic_info.gender = "male"
    state.dialogue.last_question_key = "slots.headache.red_flags.thunderclap_onset"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("uncertain red-flag answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    new_state, response, audit = handle_message(state, "不确定", 0.95)

    assert audit["extraction_source"] == "contextual_rule"
    assert "slots.headache.red_flags.thunderclap_onset" in new_state.dialogue.uncertain_slots
    assert "slots.headache.onset_speed" in new_state.dialogue.uncertain_slots
    assert response.reply != "头痛是突然一下就很痛，还是慢慢加重的？"


def test_contextual_bool_answers_do_not_call_llm(monkeypatch):
    state = create_initial_state(path_id="headache_v1")
    state.status = "in_progress"
    state.chief_complaint.main_symptoms = ["headache"]
    state.patient_basic_info.age = 30
    state.patient_basic_info.gender = "male"
    state.dialogue.last_question_key = "slots.associated_symptoms.visual_aura"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("contextual bool answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    new_state, _response, audit = handle_message(state, "没有", 0.95)

    assert audit["extraction_source"] == "contextual_rule"
    assert new_state.slots.associated_symptoms.visual_aura is False


def test_negative_medication_answer_skips_detail(monkeypatch):
    state = create_initial_state(path_id="headache_v1")
    state.status = "in_progress"
    state.chief_complaint.main_symptoms = ["headache"]
    state.patient_basic_info.age = 30
    state.patient_basic_info.gender = "male"
    state.slots.headache.red_flags.thunderclap_onset = False
    state.slots.headache.red_flags.neuro_symptoms = False
    state.slots.headache.red_flags.fever_stiff_neck = False
    state.slots.headache.red_flags.trauma_anticoag = False
    state.slots.headache.red_flags.new_onset_over_50 = False
    state.slots.headache.red_flags.worsening_pattern = False
    state.slots.headache.red_flags.pregnancy_related = False
    state.slots.headache.red_flags.eye_symptoms = False
    state.slots.headache.onset_speed = "gradual"
    state.slots.headache.location = "bilateral"
    state.slots.headache.pain_type = "distension"
    state.slots.headache.severity = "mild"
    state.slots.headache.duration_hours = "1小时"
    state.slots.headache.frequency = "daily"
    state.slots.associated_symptoms.nausea_vomiting = False
    state.slots.associated_symptoms.photophobia = False
    state.slots.associated_symptoms.visual_aura = False
    state.slots.associated_symptoms.neck_pain = False
    state.dialogue.last_question_key = "slots.medication_history.detail"

    def should_not_call_llm(text, state_dict):
        raise AssertionError("medication contextual answer should not call LLM")

    monkeypatch.setattr(
        "ai_preconsult_backend.app.services.preconsult_service.extract_slots_with_llm",
        should_not_call_llm,
    )

    new_state, response, audit = handle_message(state, "没有用药", 0.95)

    assert audit["extraction_source"] == "contextual_rule"
    assert new_state.slots.medication_history.has_used_medicine is False
    assert "slots.medication_history.detail" not in new_state.dialogue.missing_required_slots
    assert response.reply != "这次不舒服后是否已经用过药？如果用过，请说一下药名和效果。"
