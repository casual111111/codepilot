from datetime import datetime

from codepilot.session import create_session_id, list_sessions, load_session, save_session


def test_session_roundtrip(tmp_path):
    session = {
        "session_id": "20260610-001",
        "question": "Change the CLI",
        "messages": [],
        "tool_steps": [],
        "read_files": [],
        "changed_files": ["codepilot/cli.py"],
        "test_result": {"returncode": 0},
    }

    save_session(session, root=str(tmp_path))

    assert load_session("20260610-001", root=str(tmp_path))["question"] == "Change the CLI"
    assert list_sessions(root=str(tmp_path))[0]["changed_files"] == ["codepilot/cli.py"]


def test_create_session_id_is_timestamp_based():
    session_id = create_session_id(datetime(2026, 6, 10, 12, 30, 5))

    assert session_id == "20260610-123005"
