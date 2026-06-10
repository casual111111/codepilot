import json
from datetime import datetime
from pathlib import Path
from typing import Any


SESSION_DIR = Path(".codepilot") / "sessions"


def create_session_id(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y%m%d-%H%M%S")


def save_session(session: dict[str, Any], root: str = ".") -> Path:
    root_path = Path(root)
    session_id = session.get("session_id") or create_session_id()
    session["session_id"] = session_id

    session_dir = root_path / SESSION_DIR
    session_dir.mkdir(parents=True, exist_ok=True)

    path = session_dir / f"{session_id}.json"
    path.write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return path


def load_session(session_id: str, root: str = ".") -> dict[str, Any]:
    path = Path(root) / SESSION_DIR / f"{session_id}.json"

    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")

    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions(root: str = ".") -> list[dict[str, Any]]:
    session_dir = Path(root) / SESSION_DIR

    if not session_dir.exists():
        return []

    sessions: list[dict[str, Any]] = []

    for path in sorted(session_dir.glob("*.json"), reverse=True):
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        sessions.append(
            {
                "session_id": session.get("session_id", path.stem),
                "question": session.get("question", ""),
                "changed_files": session.get("changed_files", []),
                "test_result": session.get("test_result"),
            }
        )

    return sessions
