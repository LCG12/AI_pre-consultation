from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ai_preconsult_backend.app.agents.summary_agent import (
    LLMSummaryError,
    build_fallback_summary,
    generate_doctor_summary,
)
from ai_preconsult_backend.app.db.sqlite_store import (
    create_session,
    list_messages,
    load_state,
    persist_state,
    save_message,
    save_risk_hits,
)
from ai_preconsult_backend.app.models.schemas import (
    CreateSessionRequest,
    MessageRequest,
    PreconsultResponse,
)
from ai_preconsult_backend.app.services.preconsult_service import (
    create_initial_state,
    create_session_response,
    handle_message,
)


router = APIRouter(prefix="/api/preconsult", tags=["preconsult"])


@router.post("/sessions", response_model=PreconsultResponse)
def create_preconsult_session(request: CreateSessionRequest) -> PreconsultResponse:
    state = create_initial_state(
        source=request.source,
        robot_id=request.robot_id,
        location=request.location,
        path_id=request.path_id,
        age=request.age,
        gender=request.gender,
    )
    create_session(state)
    response = create_session_response(state)
    save_message(
        session_id=state.session_id,
        turn_index=0,
        role="assistant",
        message_text=response.reply,
        risk_level_at_time=response.risk_level,
    )
    return response


@router.get("/paths")
def list_paths() -> dict:
    from ai_preconsult_backend.app.services.preconsult_service import AVAILABLE_PATHS
    return {"paths": [{"id": k, **v} for k, v in AVAILABLE_PATHS.items()]}


@router.get("/paths/{path_id}/slots")
def get_path_slots(path_id: str) -> dict:
    from ai_preconsult_backend.app.core.config_loader import get_path_config
    try:
        cfg = get_path_config(path_id)
        return {"path_id": path_id, "name": cfg["name"], "required_slots": cfg["required_slots"]}
    except Exception:
        raise HTTPException(status_code=404, detail="path not found")


@router.post("/sessions/{session_id}/messages", response_model=PreconsultResponse)
def send_message(session_id: str, request: MessageRequest) -> PreconsultResponse:
    state = load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    if state.status in {"completed", "emergency", "abandoned"}:
        raise HTTPException(status_code=409, detail=f"session already {state.status}")

    turn_index = state.dialogue.turn_count + 1
    save_message(
        session_id=session_id,
        turn_index=turn_index,
        role="patient",
        message_text=request.text,
        asr_confidence=request.asr_confidence,
        risk_level_at_time=state.risk.current_level,
    )

    new_state, response, audit = handle_message(state, request.text, request.asr_confidence)
    persist_state(new_state)
    save_risk_hits(new_state)
    save_message(
        session_id=session_id,
        turn_index=new_state.dialogue.turn_count,
        role="assistant",
        message_text=response.reply,
        question_key=new_state.dialogue.last_question_key,
        extracted_slots=audit,
        risk_level_at_time=response.risk_level,
    )
    return response


@router.get("/sessions/{session_id}/result")
def get_result(session_id: str) -> dict:
    state = load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "status": state.status,
        "risk_level": state.risk.current_level,
        "risk_reasons": [hit.reason for hit in state.risk.rule_hits],
        "missing_required_slots": state.dialogue.missing_required_slots,
        "state": state.model_dump(),
    }


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str) -> dict:
    state = load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "messages": list_messages(session_id)}


@router.get("/sessions/{session_id}/doctor-summary")
def get_doctor_summary(session_id: str) -> dict:
    state = load_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    if state.status not in {"completed", "emergency"}:
        raise HTTPException(
            status_code=409,
            detail=f"session is {state.status}, summary available only for completed or emergency sessions",
        )

    state_dict = state.model_dump()
    try:
        summary = generate_doctor_summary(state_dict)
    except LLMSummaryError:
        summary = build_fallback_summary(state_dict)

    recommended_departments = _get_departments(state_dict)
    return {
        "session_id": session_id,
        "status": "generated",
        "generation_method": summary.get("generation_method", "llm"),
        "summary": summary,
        "recommended_departments": recommended_departments,
        "disclaimer": "本摘要由AI生成，仅供医生接诊参考，不能替代专业医疗判断。",
    }


def _get_departments(state_dict: dict) -> list[str]:
    from ai_preconsult_backend.app.engines.triage_engine import recommend_departments
    departments, _ = recommend_departments(state_dict)
    return departments
