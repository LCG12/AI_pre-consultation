from fastapi.testclient import TestClient

from ai_preconsult_backend.app.main import app


client = TestClient(app)


def test_create_session_and_send_message():
    create_response = client.post(
        "/api/preconsult/sessions",
        json={"source": "robot", "robot_id": "robot_001", "location": "门诊大厅"},
    )

    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    message_response = client.post(
        f"/api/preconsult/sessions/{session_id}/messages",
        json={"text": "我发烧三天，还咳嗽嗓子疼", "asr_confidence": 0.91},
    )

    assert message_response.status_code == 200
    body = message_response.json()
    assert body["session_id"] == session_id
    assert body["risk_level"] == "yellow"
    assert body["status"] in {"in_progress", "completed"}
