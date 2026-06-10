import json
from typing import Any

from codepilot.context import SYSTEM_PROMPT, compact_messages


class AgentContext:
    def __init__(
        self,
        user_question: str,
        max_messages: int = 20,
        max_tool_output_chars: int = 12000,
    ):
        self.user_question = user_question
        self.messages: list[dict] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_question,
            },
        ]
        self.tool_steps: list[dict[str, Any]] = []
        self.read_files: set[str] = set()
        self.max_messages = max_messages
        self.max_tool_output_chars = max_tool_output_chars

    def add_assistant_message(self, message: dict) -> None:
        self.messages.append(message)
        self.compact()

    def add_tool_message(
        self,
        tool_call_id: str,
        tool_name: str,
        content: str,
    ) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": self.truncate_tool_output(content),
            }
        )
        self.compact()

    def add_tool_step(
        self,
        name: str,
        arguments: str,
        result: str,
        success: bool,
    ) -> int:
        step = len(self.tool_steps) + 1
        parsed_arguments = _parse_arguments(arguments)
        truncated_result = self.truncate_tool_output(result)

        self.tool_steps.append(
            {
                "step": step,
                "tool": name,
                "arguments": parsed_arguments,
                "result_preview": truncated_result[:1000],
                "success": success,
            }
        )

        if name == "read_file" and success:
            path = parsed_arguments.get("path")
            if isinstance(path, str):
                self.read_files.add(path)

        return step

    def truncate_tool_output(self, text: str) -> str:
        if len(text) <= self.max_tool_output_chars:
            return text

        return (
            text[: self.max_tool_output_chars]
            + f"\n\n[Tool output truncated to {self.max_tool_output_chars} characters]"
        )

    def compact(self) -> None:
        self.messages = compact_messages(self.messages, self.max_messages)

    def to_session_dict(
        self,
        session_id: str | None = None,
        changed_files: list[str] | None = None,
        test_result: dict | None = None,
    ) -> dict:
        return {
            "session_id": session_id,
            "question": self.user_question,
            "messages": self.messages,
            "tool_steps": self.tool_steps,
            "read_files": sorted(self.read_files),
            "changed_files": changed_files or [],
            "test_result": test_result,
        }


def _parse_arguments(arguments: str) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"_raw": arguments}

    if isinstance(parsed, dict):
        return parsed

    return {"_value": parsed}
