from rich.console import Console
from rich.panel import Panel

from codepilot.config import CodePilotConfig
from codepilot.context import build_initial_messages, compact_messages
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
        show_tool_calls: bool = True,
    ):
        self.config = config
        self.max_turns = max_turns
        self.show_tool_calls = show_tool_calls
        self.tools = get_tool_definitions()

    def run(self, user_question: str) -> str:
        messages = build_initial_messages(user_question)

        for turn in range(1, self.max_turns + 1):
            messages = compact_messages(messages)

            try:
                assistant_message = chat_completion(
                    messages=messages,
                    config=self.config,
                    tools=self.tools,
                    tool_choice="auto",
                )
            except LLMError as e:
                raise AgentRuntimeError(str(e)) from e

            messages.append(assistant_message)

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

                if self.show_tool_calls:
                    console.print(
                        Panel.fit(
                            tool_args,
                            title=f"Tool Call: {tool_name}",
                            border_style="cyan",
                        )
                    )

                tool_result = execute_tool(tool_name, tool_args)

                if self.show_tool_calls:
                    console.print(
                        Panel.fit(
                            tool_result[:2000],
                            title=f"Tool Result: {tool_name}",
                            border_style="green",
                        )
                    )

                messages.append(
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
