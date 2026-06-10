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
        max_repo_map_calls: int = 1,
        show_tool_calls: bool = True,
    ):
        self.config = config
        self.max_turns = max_turns
        self.max_repo_map_calls = max_repo_map_calls
        self.show_tool_calls = show_tool_calls
        self.tools = get_tool_definitions()

    def run(self, user_question: str) -> str:
        context = AgentContext(user_question=user_question)
        step = 0
        repo_map_calls = 0

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
                    console.print(f"[{step}] tool_call: {tool_name} {_format_arguments(tool_args)}")

                if tool_name == "repo_map":
                    repo_map_calls += 1
                    if repo_map_calls > self.max_repo_map_calls:
                        tool_result = (
                            "Tool repo_map skipped: repo_map was already called. "
                            "Use grep_search or read_file for narrower follow-up context."
                        )
                    else:
                        tool_result = execute_tool(tool_name, tool_args)
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
