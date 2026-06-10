import json
from dataclasses import dataclass

from rich.console import Console

from codepilot.agent_context import AgentContext
from codepilot.config import CodePilotConfig
from codepilot.llm import LLMError, chat_completion
from codepilot.tools.registry import execute_tool, get_tool_definitions

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
        self.tools = get_tool_definitions()
        self.last_context: AgentContext | None = None

    def run(self, user_question: str) -> AgentResult:
        context = AgentContext(user_question=user_question)
        self.last_context = context
        tool_call_counts: dict[str, int] = {}
        read_file_count = 0

        for turn in range(1, self.max_turns + 1):
            context.compact()

            try:
                assistant_message = chat_completion(
                    messages=context.messages,
                    config=self.config,
                    tools=self.tools,
                    tool_choice="auto",
                )
            except LLMError as e:
                raise AgentRuntimeError(str(e)) from e

            context.add_assistant_message(assistant_message)

            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                answer = assistant_message.get("content") or ""
                return AgentResult(
                    answer=answer,
                    session=context.to_session_dict(),
                )

            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                tool_name = function.get("name")
                tool_args = function.get("arguments") or "{}"
                tool_call_id = tool_call.get("id")

                if not tool_name:
                    continue

                if not tool_call_id:
                    tool_call_id = f"tool-call-{turn}-{len(context.tool_steps) + 1}"

                tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1
                max_calls = self.max_tool_calls_per_name.get(tool_name, 3)

                if tool_call_counts[tool_name] > max_calls:
                    tool_result = (
                        f"Tool {tool_name} skipped: call limit reached "
                        f"({max_calls}). Use existing context or choose a different tool."
                    )
                elif tool_name == "read_file" and read_file_count >= self.max_read_file_per_run:
                    tool_result = (
                        "Tool read_file skipped: max_read_file_per_run reached "
                        f"({self.max_read_file_per_run}). Use already-read files or grep_search."
                    )
                else:
                    tool_result = execute_tool(tool_name, tool_args)
                    if tool_name == "read_file":
                        read_file_count += 1

                tool_result = context.truncate_tool_output(tool_result)
                success = _tool_succeeded(tool_result)
                step = context.add_tool_step(
                    name=tool_name,
                    arguments=tool_args,
                    result=tool_result,
                    success=success,
                )

                if self.show_tool_calls:
                    console.print(f"[Step {step}] {tool_name} {_format_arguments(tool_args)}")

                context.add_tool_message(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    content=tool_result,
                )

        answer = (
            "Agent stopped because it reached the maximum number of turns. "
            "Try asking a narrower question."
        )
        return AgentResult(
            answer=answer,
            session=context.to_session_dict(),
        )


def _format_arguments(arguments_json: str) -> str:
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return arguments_json

    return json.dumps(arguments, ensure_ascii=False)


def _tool_succeeded(result: str) -> bool:
    failure_prefixes = (
        "Unknown tool:",
        "Invalid tool arguments JSON:",
        "Tool ",
    )
    return not result.startswith(failure_prefixes)
