import json
from dataclasses import dataclass

from rich.console import Console

from codepilot.agent_context import AgentContext
from codepilot.config import CodePilotConfig
from codepilot.llm import LLMError, chat_completion
from codepilot.tools.registry import execute_tool_action, format_tools_for_prompt

console = Console()


class AgentRuntimeError(Exception):
    pass


@dataclass
class AgentResult:
    answer: str
    session: dict


class CodePilotAgent:
    def __init__(
        self,
        config: CodePilotConfig,
        max_turns: int = 8,
        max_tool_calls_per_name: dict[str, int] | None = None,
        max_read_file_per_run: int = 12,
        show_tool_calls: bool = True,
        allow_write: bool = False,
    ):
        self.config = config
        self.max_turns = max_turns
        self.max_read_file_per_run = max_read_file_per_run
        self.max_tool_calls_per_name = max_tool_calls_per_name or {
            "repo_map": 1,
            "list_files": 2,
            "grep_search": 5,
            "read_file": 12,
            "git_status": 3,
            "git_diff": 3,
            "run_tests": 2,
        }
        self.show_tool_calls = show_tool_calls
        self.allow_write = allow_write
        self.tools_prompt = format_tools_for_prompt(allow_write=allow_write)
        self.last_context: AgentContext | None = None
        self.conversation_history: list[dict] = []

    def run(self, user_question: str) -> AgentResult:
        context = AgentContext(
            user_question=user_question,
            prior_messages=self.conversation_history,
        )
        context.add_user_message(_build_tool_instructions(self.tools_prompt))
        self.last_context = context
        tool_call_counts: dict[str, int] = {}
        read_file_count = 0

        for turn in range(1, self.max_turns + 1):
            context.compact()

            try:
                assistant_message = chat_completion(
                    messages=context.messages,
                    config=self.config,
                )
            except LLMError as e:
                raise AgentRuntimeError(str(e)) from e

            context.add_assistant_message(assistant_message)

            decision = _parse_agent_decision(assistant_message.get("content") or "")
            action = decision.get("action")

            if action == "final":
                answer = str(decision.get("answer") or "")
                self._remember_exchange(user_question, answer)
                return AgentResult(
                    answer=answer,
                    session=context.to_session_dict(),
                )

            if action != "tool":
                context.add_user_message(
                    "Invalid response. Return only JSON with action 'tool' or 'final'."
                )
                continue

            tool_name = str(decision.get("tool_name") or "")
            tool_arguments = decision.get("arguments") or {}

            if not isinstance(tool_arguments, dict):
                tool_arguments = {}

            if not tool_name:
                context.add_user_message(
                    "Invalid tool action. Provide tool_name and arguments."
                )
                continue

            tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1
            max_calls = self.max_tool_calls_per_name.get(tool_name, 3)

            if tool_call_counts[tool_name] > max_calls:
                tool_result = (
                    f"Tool {tool_name} skipped: call limit reached "
                    f"({max_calls}). Use existing context or choose a different tool."
                )
                success = False
            elif tool_name == "read_file" and read_file_count >= self.max_read_file_per_run:
                tool_result = (
                    "Tool read_file skipped: max_read_file_per_run reached "
                    f"({self.max_read_file_per_run}). Use already-read files or grep_search."
                )
                success = False
            else:
                result = execute_tool_action(
                    tool_name,
                    tool_arguments,
                    allow_write=self.allow_write,
                )
                success = result.success
                tool_result = result.content if result.success else result.error or ""

                if tool_name == "read_file" and success:
                    read_file_count += 1

            tool_result = context.truncate_tool_output(tool_result)
            tool_args_json = json.dumps(tool_arguments, ensure_ascii=False)
            step = context.add_tool_step(
                name=tool_name,
                arguments=tool_args_json,
                result=tool_result,
                success=success,
            )

            if self.show_tool_calls:
                console.print(f"[Step {step}] {tool_name} {tool_args_json}")

            context.add_observation_message(
                tool_name=tool_name,
                content=tool_result,
            )

        answer = (
            "Agent stopped because it reached the maximum number of turns. "
            "Try asking a narrower question."
        )
        self._remember_exchange(user_question, answer)
        return AgentResult(
            answer=answer,
            session=context.to_session_dict(),
        )

    def _remember_exchange(self, user_question: str, answer: str) -> None:
        self.conversation_history.extend(
            [
                {"role": "user", "content": user_question},
                {"role": "assistant", "content": answer},
            ]
        )

        if len(self.conversation_history) > 12:
            self.conversation_history = self.conversation_history[-12:]


def _build_tool_instructions(tools_prompt: str) -> str:
    return (
        "Use the following tools by returning exactly one JSON object.\n\n"
        "Available tools:\n"
        f"{tools_prompt}\n\n"
        "To call a tool, return:\n"
        '{"action":"tool","tool_name":"read_file","arguments":{"path":"README.md"}}\n\n'
        "To answer the user, return:\n"
        '{"action":"final","answer":"your answer"}\n\n'
        "Return JSON only. Do not use Markdown outside the JSON."
    )


def _parse_agent_decision(content: str) -> dict:
    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed

    return {}
