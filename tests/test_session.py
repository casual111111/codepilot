from datetime import datetime

from codepilot.session import create_session_id, list_sessions, load_session, save_session


def test_session_roundtrip(tmp_path):
    session = {
        "session_id": "20260610-001",
        "question": "Change the CLI",
        "messages": [],
        "tool_steps": [{"step": 1, "tool": "repo_map"}],
        "read_files": ["pyproject.toml"],
        "changed_files": ["codepilot/cli.py"],
        "test_result": {"returncode": 0},
    }

    save_session(session, root=str(tmp_path))

    assert load_session("20260610-001", root=str(tmp_path))["question"] == "Change the CLI"
    listed_session = list_sessions(root=str(tmp_path))[0]

    assert listed_session["changed_files"] == ["codepilot/cli.py"]
    assert listed_session["tool_steps_count"] == 1
    assert listed_session["read_files_count"] == 1


def test_create_session_id_is_timestamp_based():
    session_id = create_session_id(datetime(2026, 6, 10, 12, 30, 5))

    assert session_id == "20260610-123005"
