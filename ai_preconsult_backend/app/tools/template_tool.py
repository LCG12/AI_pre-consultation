from __future__ import annotations

from typing import Any

from ai_preconsult_backend.app.core.config_loader import (
    get_patient_report_templates,
    get_question_templates,
)


def build_question(question_key: str) -> tuple[str, list[str]]:
    templates = get_question_templates()
    reply = templates.get(question_key, "请再补充说明一下目前主要不舒服的情况。")
    quick_replies = ["有", "没有", "不确定"] if "red_flag" in question_key else []
    return reply, quick_replies


def build_patient_report(
    risk_level: str,
    risk_reasons: list[str],
    recommended_departments: list[str],
) -> dict[str, Any]:
    templates = get_patient_report_templates()
    message = templates.get(risk_level, templates["green"])
    if risk_reasons and risk_level in {"yellow", "red"}:
        message = f"{message} 主要原因：{'；'.join(risk_reasons)}。"
    if recommended_departments:
        message = f"{message} 可优先选择：{'、'.join(recommended_departments)}。"

    return {
        "message": message,
        "preparation": ["记录体温变化", "准备已用药名称", "说明过敏史", "带上既往检查结果"],
    }


def build_emergency_reply(reasons: list[str]) -> str:
    reason_text = "、".join(reasons) if reasons else "需要尽快处理的风险信号"
    return f"您提到{reason_text}，这属于需要尽快处理的风险信号。请立即联系现场医护人员，或前往急诊。"
