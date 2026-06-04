from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["unknown", "green", "yellow", "red"]
SessionStatus = Literal["created", "in_progress", "completed", "emergency", "abandoned", "error"]


class RobotContext(BaseModel):
    robot_id: str | None = None
    location: str | None = None


class ChiefComplaint(BaseModel):
    raw_text: str = ""
    main_symptoms: list[str] = Field(default_factory=list)
    duration_days: int | None = None


class PatientBasicInfo(BaseModel):
    age: int | None = None
    gender: str | None = None
    pregnancy_status: bool | None = None


class FeverSlots(BaseModel):
    duration_days: int | None = None
    max_temperature_c: float | None = None
    current_temperature_c: float | None = None


class CoughSlots(BaseModel):
    has_cough: bool | None = None
    cough_type: str | None = None
    sputum: str | None = None


class AbdominalPainSlots(BaseModel):
    location: str | None = None
    pain_type: str | None = None
    severity: str | None = None
    duration_hours: float | str | None = None
    radiation: str | None = None
    onset: str | None = None
    eating_relationship: str | None = None
    bowel_movement: str | None = None


class HeadacheRedFlags(BaseModel):
    thunderclap_onset: bool | None = None
    neuro_symptoms: bool | None = None
    fever_stiff_neck: bool | None = None
    trauma_anticoag: bool | None = None
    new_onset_over_50: bool | None = None
    worsening_pattern: bool | None = None
    pregnancy_related: bool | None = None
    eye_symptoms: bool | None = None


class HeadacheSlots(BaseModel):
    onset_speed: str | None = None
    location: str | None = None
    pain_type: str | None = None
    severity: str | None = None
    duration_hours: float | str | None = None
    frequency: str | None = None
    red_flags: HeadacheRedFlags = Field(default_factory=HeadacheRedFlags)


class AssociatedSymptoms(BaseModel):
    sore_throat: bool | None = None
    fatigue: bool | None = None
    headache: bool | None = None
    diarrhea: bool | None = None
    rash: bool | None = None
    nausea_vomiting: bool | None = None
    constipation: bool | None = None
    fever: bool | None = None
    photophobia: bool | None = None
    visual_aura: bool | None = None
    neck_pain: bool | None = None


class RedFlags(BaseModel):
    shortness_of_breath: bool | None = None
    chest_pain: bool | None = None
    hemoptysis: bool | None = None
    confusion: bool | None = None
    seizure: bool | None = None
    cyanosis: bool | None = None
    peritoneal_signs: bool | None = None
    hematemesis: bool | None = None
    melena: bool | None = None
    syncope: bool | None = None


class AllergyHistory(BaseModel):
    has_allergy: bool | None = None
    detail: str | None = None


class MedicationHistory(BaseModel):
    has_used_medicine: bool | None = None
    detail: str | None = None


class Slots(BaseModel):
    fever: FeverSlots = Field(default_factory=FeverSlots)
    cough: CoughSlots = Field(default_factory=CoughSlots)
    abdominal_pain: AbdominalPainSlots = Field(default_factory=AbdominalPainSlots)
    headache: HeadacheSlots = Field(default_factory=HeadacheSlots)
    associated_symptoms: AssociatedSymptoms = Field(default_factory=AssociatedSymptoms)
    red_flags: RedFlags = Field(default_factory=RedFlags)
    past_history: dict[str, Any] = Field(default_factory=dict)
    allergy_history: AllergyHistory = Field(default_factory=AllergyHistory)
    medication_history: MedicationHistory = Field(default_factory=MedicationHistory)


class RuleHit(BaseModel):
    rule_id: str
    rule_name: str
    risk_level: str
    reason: str
    trigger_field: str | None = None
    trigger_value: Any = None


class RiskState(BaseModel):
    current_level: RiskLevel = "unknown"
    rule_hits: list[RuleHit] = Field(default_factory=list)


class DialogueState(BaseModel):
    turn_count: int = 0
    max_turns: int = 5
    missing_required_slots: list[str] = Field(default_factory=list)
    last_question_key: str | None = None
    skipped_slots: list[str] = Field(default_factory=list)
    pending_confirmation: dict | None = None
    question_retries: dict[str, int] = Field(default_factory=dict)


class PreconsultState(BaseModel):
    session_id: str
    status: SessionStatus = "created"
    source: str = "robot"
    robot_context: RobotContext = Field(default_factory=RobotContext)
    path_id: str = "fever_cough_v1"
    chief_complaint: ChiefComplaint = Field(default_factory=ChiefComplaint)
    patient_basic_info: PatientBasicInfo = Field(default_factory=PatientBasicInfo)
    slots: Slots = Field(default_factory=Slots)
    risk: RiskState = Field(default_factory=RiskState)
    dialogue: DialogueState = Field(default_factory=DialogueState)


class CreateSessionRequest(BaseModel):
    source: str = "robot"
    robot_id: str | None = None
    location: str | None = None
    path_id: str | None = None
    age: int | None = None
    gender: str | None = None


class MessageRequest(BaseModel):
    text: str
    asr_confidence: float | None = None


class PreconsultResponse(BaseModel):
    session_id: str
    status: SessionStatus
    reply: str
    display_text: str
    quick_replies: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "unknown"
    risk_reasons: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    recommended_departments: list[str] = Field(default_factory=list)
    should_stop_dialogue: bool = False
    patient_report: dict[str, Any] | None = None
    doctor_summary_status: str | None = None
