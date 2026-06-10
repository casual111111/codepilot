import json
from dataclasses import dataclass
from typing import Any, Callable

from codepilot.repo_map import build_repo_map
from codepilot.tools.filesystem import (
    create_directory,
    list_project_files,
    read_text_file,
    write_text_file,
)
from codepilot.tools.git import git_diff, git_status
from codepilot.tools.search import grep_search
from codepilot.tools.shell import run_tests


MAX_TOOL_OUTPUT_CHARS = 12000


@dataclass
class ToolResult:
    success: bool
    content: str
    error: str | None = None


def truncate_text(text: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + f"\n\n[Tool output truncated to {max_chars} characters]"


def tool_list_files() -> str:
    files = list_project_files(".")
    return "\n".join(files)


def tool_read_file(path: str) -> str:
    content = read_text_file(path, max_chars=MAX_TOOL_OUTPUT_CHARS)
    return content


def tool_grep_search(query: str, max_results: int = 30) -> str:
    results = grep_search(query=query, max_results=max_results)

    if not results:
        return f"No results found for query: {query}"

    lines: list[str] = []

    for item in results:
        lines.append(
            f"{item['path']}:{item['line']}: {item['content']}"
        )

    return "\n".join(lines)


def tool_repo_map() -> str:
    repo_map = build_repo_map(".")

    lines: list[str] = []
    lines.append(f"Root: {repo_map['root']}")
    lines.append(f"File count: {repo_map['file_count']}")
    lines.append("")

    for item in repo_map["files"]:
        symbols = item.get("symbols") or []

        if symbols:
            symbol_text = ", ".join(symbols[:12])
            lines.append(
                f"- {item['path']} [{item['language']}] symbols: {symbol_text}"
            )
        else:
            lines.append(f"- {item['path']} [{item['language']}]")

    return "\n".join(lines)


def tool_git_status() -> str:
    return git_status()


def tool_git_diff() -> str:
    return git_diff()


def tool_run_tests(command: str = "pytest") -> str:
    result = run_tests(command)

    output = []
    output.append(f"Command: {result['command']}")
    output.append(f"Return code: {result['returncode']}")
    output.append(f"Timed out: {result['timed_out']}")
    output.append("")

    if result["stdout"]:
        output.append("[stdout]")
        output.append(result["stdout"])

    if result["stderr"]:
        output.append("[stderr]")
        output.append(result["stderr"])

    return truncate_text("\n".join(output))


def tool_create_directory(path: str) -> str:
    return create_directory(path)


def tool_write_file(path: str, content: str) -> str:
    return write_text_file(path, content)


TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "list_files": tool_list_files,
    "read_file": tool_read_file,
    "grep_search": tool_grep_search,
    "repo_map": tool_repo_map,
    "git_status": tool_git_status,
    "git_diff": tool_git_diff,
    "run_tests": tool_run_tests,
    "create_directory": tool_create_directory,
    "write_file": tool_write_file,
}


NO_ARGUMENT_TOOLS = {
    "list_files",
    "repo_map",
    "git_status",
    "git_diff",
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """
    OpenAI-compatible tool definitions.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "repo_map",
                "description": "Build a lightweight map of the current repository, including files and Python symbols.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List project files under the current repository.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a text file from the current repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path of the file to read, for example codepilot/cli.py.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "grep_search",
                "description": "Search for a keyword in project files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Keyword to search for.",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of search results.",
                            "default": 30,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Show current git working tree status.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff",
                "description": "Show current unstaged git diff.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "Run the project's test command and return stdout/stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Test command to run, for example pytest or python -m compileall codepilot.",
                            "default": "pytest",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_directory",
                "description": "Create a directory inside the current repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path to create.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write a UTF-8 text file inside the current repository, creating parent directories if needed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative file path to write.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete file content.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
    ]


def execute_tool(name: str, arguments_json: str) -> str:
    """
    Execute a registered tool by name.
    """

    if name not in TOOL_HANDLERS:
        return f"Unknown tool: {name}"

    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return f"Invalid tool arguments JSON: {arguments_json}"

    handler = TOOL_HANDLERS[name]

    try:
        if name in NO_ARGUMENT_TOOLS:
            result = handler()
            return truncate_text(str(result))

        result = handler(**arguments)
    except Exception as e:
        return f"Tool {name} failed: {type(e).__name__}: {e}"

    return truncate_text(str(result))


def execute_tool_action(name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
    """
    Execute a tool from an agent JSON action.
    """
    if name not in TOOL_HANDLERS:
        return ToolResult(
            success=False,
            content="",
            error=f"Unknown tool: {name}",
        )

    handler = TOOL_HANDLERS[name]
    arguments = arguments or {}

    try:
        if name in NO_ARGUMENT_TOOLS:
            result = handler()
        else:
            result = handler(**arguments)
    except Exception as e:
        return ToolResult(
            success=False,
            content="",
            error=f"Tool {name} failed: {type(e).__name__}: {e}",
        )

    return ToolResult(
        success=True,
        content=truncate_text(str(result)),
    )


def format_tools_for_prompt() -> str:
    lines = []

    for tool in get_tool_definitions():
        function = tool["function"]
        name = function["name"]
        description = function["description"]
        properties = function["parameters"].get("properties") or {}
        required = set(function["parameters"].get("required") or [])

        if properties:
            args = ", ".join(
                f"{arg}{'*' if arg in required else ''}: {spec.get('type', 'any')}"
                for arg, spec in properties.items()
            )
        else:
            args = "no arguments"

        lines.append(f"- {name}({args}): {description}")

    return "\n".join(lines)
