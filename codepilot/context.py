SYSTEM_PROMPT = """
You are CodePilot CLI, a lightweight coding agent running inside a local repository.

You can use tools to inspect the repository.
You should not guess file contents.
When you need details, call read_file or grep_search.
When you need the project structure, call repo_map.
When the user asks about current changes, call git_status or git_diff.
When the user asks about tests, call run_tests.

Rules:
1. Prefer using tools before answering repository-specific questions.
2. Do not read unnecessary files.
3. Keep answers concise and practical.
4. Explain what you found based on tool results.
5. If the context is insufficient, say what file or command should be inspected next.
6. Do not claim you changed files unless a patch/apply tool exists and was used.
""".strip()


class AgentContext:
    def __init__(
        self,
        user_question: str,
        max_messages: int = 20,
        max_tool_output_chars: int = 12000,
    ):
        self.messages: list[dict] = build_initial_messages(user_question)
        self.tool_steps: list[dict] = []
        self.read_files: set[str] = set()
        self.max_messages = max_messages
        self.max_tool_output_chars = max_tool_output_chars

    def append_message(self, message: dict) -> None:
        self.messages.append(message)
        self.compact()

    def record_tool_call(
        self,
        step: int,
        name: str,
        arguments: str,
        result: str,
    ) -> str:
        truncated_result = self.truncate_tool_output(result)

        self.tool_steps.append(
            {
                "step": step,
                "name": name,
                "arguments": arguments,
                "result": truncated_result,
            }
        )

        if name == "read_file":
            path = _extract_read_path(arguments)
            if path:
                self.read_files.add(path)

        return truncated_result

    def truncate_tool_output(self, text: str) -> str:
        if len(text) <= self.max_tool_output_chars:
            return text

        return (
            text[: self.max_tool_output_chars]
            + f"\n\n[Tool output truncated to {self.max_tool_output_chars} characters]"
        )

    def compact(self) -> None:
        self.messages = compact_messages(self.messages, self.max_messages)


def build_initial_messages(user_question: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_question,
        },
    ]


def compact_messages(messages: list[dict], max_messages: int = 20) -> list[dict]:
    """
    Very simple context compaction.

    Keep:
    - system message
    - latest max_messages messages
    """
    if len(messages) <= max_messages:
        return messages

    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    recent_messages = messages[-max_messages:]

    if system_messages:
        return [system_messages[0], *recent_messages]

    return recent_messages


def _extract_read_path(arguments: str) -> str | None:
    import json

    try:
        data = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return None

    path = data.get("path")
    if isinstance(path, str):
        return path

    return None
