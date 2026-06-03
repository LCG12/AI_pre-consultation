from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_preconsult_backend.app.models.schemas import PreconsultState


DB_PATH = Path(__file__).resolve().parents[2] / "preconsult.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS preconsult_sessions (
              session_code TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              source TEXT,
              robot_id TEXT,
              location TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS preconsult_states (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_code TEXT NOT NULL,
              state_json TEXT NOT NULL,
              version INTEGER DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS preconsult_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_code TEXT NOT NULL,
              turn_index INTEGER NOT NULL,
              role TEXT NOT NULL,
              message_text TEXT NOT NULL,
              asr_confidence REAL,
              question_key TEXT,
              extracted_slots TEXT,
              risk_level_at_time TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_rule_hits (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_code TEXT NOT NULL,
              rule_id TEXT,
              rule_name TEXT,
              trigger_field TEXT,
              trigger_value TEXT,
              risk_level TEXT,
              reason TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS doctor_summaries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_code TEXT NOT NULL,
              summary_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )


def create_session(state: PreconsultState) -> None:
    init_db()
    now = utc_now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO preconsult_sessions (
              session_code, status, source, robot_id, location, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.session_id,
                state.status,
                state.source,
                state.robot_context.robot_id,
                state.robot_context.location,
                now,
                now,
            ),
        )
        save_state(connection, state)


def save_state(connection: sqlite3.Connection, state: PreconsultState) -> None:
    now = utc_now()
    latest = connection.execute(
        "SELECT version FROM preconsult_states WHERE session_code = ? ORDER BY version DESC LIMIT 1",
        (state.session_id,),
    ).fetchone()
    version = int(latest["version"]) + 1 if latest else 1
    connection.execute(
        """
        INSERT INTO preconsult_states (session_code, state_json, version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            state.session_id,
            json.dumps(state.model_dump(), ensure_ascii=False),
            version,
            now,
            now,
        ),
    )
    connection.execute(
        "UPDATE preconsult_sessions SET status = ?, updated_at = ? WHERE session_code = ?",
        (state.status, now, state.session_id),
    )


def persist_state(state: PreconsultState) -> None:
    with get_connection() as connection:
        save_state(connection, state)


def load_state(session_id: str) -> PreconsultState | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT state_json FROM preconsult_states
            WHERE session_code = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return PreconsultState.model_validate(json.loads(row["state_json"]))


def save_message(
    session_id: str,
    turn_index: int,
    role: str,
    message_text: str,
    asr_confidence: float | None = None,
    question_key: str | None = None,
    extracted_slots: dict[str, Any] | None = None,
    risk_level_at_time: str | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO preconsult_messages (
              session_code, turn_index, role, message_text, asr_confidence, question_key,
              extracted_slots, risk_level_at_time, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                turn_index,
                role,
                message_text,
                asr_confidence,
                question_key,
                json.dumps(extracted_slots or {}, ensure_ascii=False),
                risk_level_at_time,
                utc_now(),
            ),
        )


def save_risk_hits(state: PreconsultState) -> None:
    with get_connection() as connection:
        for hit in state.risk.rule_hits:
            connection.execute(
                """
                INSERT INTO risk_rule_hits (
                  session_code, rule_id, rule_name, trigger_field, trigger_value,
                  risk_level, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.session_id,
                    hit.rule_id,
                    hit.rule_name,
                    hit.trigger_field,
                    json.dumps(hit.trigger_value, ensure_ascii=False),
                    hit.risk_level,
                    hit.reason,
                    utc_now(),
                ),
            )


def list_messages(session_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT turn_index, role, message_text, asr_confidence, question_key,
                   extracted_slots, risk_level_at_time, created_at
            FROM preconsult_messages
            WHERE session_code = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]
