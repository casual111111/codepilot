import json

from rich.console import Console

from codepilot.config import CodePilotConfig
from codepilot.context import AgentContext
from codepilot.llm import LLMError, chat_completion
from codepilot.tools.registry import execute_tool, get_tool_definitions

console = Console()


class AgentRuntimeError(Exception):
    pass


class CodePilotAgent:
    def __init__(
        self,
        config: CodePilotConfig,
        max_turns: int = 8,
        max_tool_calls_per_name: dict[str, int] | None = None,
        show_tool_calls: bool = True,
    ):
        self.config = config
        self.max_turns = max_turns
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

    def run(self, user_question: str) -> str:
        context = AgentContext(user_question=user_question)
        self.last_context = context
        step = 0
        tool_call_counts: dict[str, int] = {}

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

            context.append_message(assistant_message)

            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                return assistant_message.get("content") or ""

            for tool_call in tool_calls:
                function = tool_call.get("function") or {}
                tool_name = function.get("name")
                tool_args = function.get("arguments") or "{}"
                tool_call_id = tool_call.get("id")

                if not tool_name:
                    continue

                if not tool_call_id:
                    tool_call_id = f"tool-call-{turn}-{step + 1}"

                step += 1

                if self.show_tool_calls:
                    console.print(f"[Step {step}] {tool_name} {_format_arguments(tool_args)}")

                tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1
                max_calls = self.max_tool_calls_per_name.get(tool_name, 3)

                if tool_call_counts[tool_name] > max_calls:
                    tool_result = (
                        f"Tool {tool_name} skipped: call limit reached "
                        f"({max_calls}). Use existing context or choose a different tool."
                    )
                else:
                    tool_result = execute_tool(tool_name, tool_args)

                tool_result = context.record_tool_call(
                    step=step,
                    name=tool_name,
                    arguments=tool_args,
                    result=tool_result,
                )

                context.append_message(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_result,
                    }
                )

        return (
            "Agent stopped because it reached the maximum number of turns. "
            "Try asking a narrower question."
        )


def _format_arguments(arguments_json: str) -> str:
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return arguments_json

    return json.dumps(arguments, ensure_ascii=False)
