from pathlib import Path
import difflib
import json
import re

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from codepilot.agent import AgentResult, AgentRuntimeError, CodePilotAgent
from codepilot.config import load_config
from codepilot.llm import LLMError
from codepilot.repo_map import save_repo_map
from codepilot.session import create_session_id, list_sessions, load_session, save_session
from codepilot.tools.git import git_diff, git_status
from codepilot.tools.filesystem import list_project_files, read_text_file
from codepilot.tools.patch import apply_patch, extract_changed_files, generate_patch
from codepilot.tools.search import grep_search
from codepilot.tools.shell import run_tests

app = typer.Typer(
    name="codepilot",
    help="CodePilot CLI - A lightweight coding agent for local repositories.",
)

console = Console()


def detect_language(path: str) -> str:
    suffix = Path(path).suffix.lower()

    if suffix == ".py":
        return "python"
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix == ".md":
        return "markdown"
    if suffix in {".yaml", ".yml"}:
        return "yaml"

    return "text"


def collect_edit_context(instruction: str) -> AgentResult:
    """Use the agent to inspect files relevant to an edit request."""
    config = load_config()
    agent = CodePilotAgent(config=config)
    context_question = (
        "You are collecting context for a code edit. "
        "Use repo_map, grep_search, and read_file to identify and read every file "
        "needed to safely implement the request. "
        "Do not propose a patch. Finish with a concise summary of the files read.\n\n"
        f"Edit request:\n{instruction}"
    )
    return agent.run(context_question)


def read_edit_files(paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}

    for path in paths:
        file_path = Path(path)

        if not file_path.is_file():
            continue

        files[path] = file_path.read_text(encoding="utf-8", errors="replace")

    return files


def format_edit_files(files: dict[str, str]) -> str:
    sections: list[str] = []

    for path, content in files.items():
        sections.append(
            f"--- FILE: {path} ---\n"
            f"{content}\n"
            f"--- END FILE: {path} ---"
        )

    return "\n\n".join(sections)


def build_edit_messages(
    edit_prompt: str,
    instruction: str,
    file_contents: dict[str, str],
    current_diff: str,
    previous_patch: str | None = None,
    patch_error: str | None = None,
) -> list[dict]:
    retry_context = ""

    if previous_patch is not None and patch_error is not None:
        retry_context = (
            "\n\nPrevious patch failed git apply --check.\n"
            f"Previous patch:\n{previous_patch}\n\n"
            f"git apply --check output:\n{patch_error}\n\n"
            "Generate a corrected unified diff using only the provided files."
        )

    return [
        {"role": "system", "content": edit_prompt},
        {
            "role": "user",
            "content": (
                f"User request:\n{instruction}\n\n"
                f"Provided file contents:\n{format_edit_files(file_contents)}\n\n"
                f"Current unstaged diff:\n{current_diff}\n"
                f"{retry_context}"
            ),
        },
    ]


def normalize_patch(patch: str) -> str:
    patch = patch.strip()
    lines = patch.splitlines()

    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    normalized_lines: list[str] = []
    hunk_header_pattern = re.compile(r"^(@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@) (.+)$")

    for line in lines:
        match = hunk_header_pattern.match(line)

        if match:
            normalized_lines.append(match.group(1))
            normalized_lines.append(f" {match.group(2)}")
            continue

        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip() + "\n"


def rebuild_patch_from_contents(patch: str, file_contents: dict[str, str]) -> str | None:
    patched_files: dict[str, str] = {}
    current_path: str | None = None
    hunk_lines: list[str] = []

    def flush_hunk() -> bool:
        if current_path is None or not hunk_lines:
            return True

        original = patched_files.get(current_path, file_contents.get(current_path))

        if original is None:
            return False

        updated = apply_hunk_to_text(original, hunk_lines)

        if updated is None:
            return False

        patched_files[current_path] = updated
        hunk_lines.clear()
        return True

    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            if not flush_hunk():
                return None

            current_path = line.removeprefix("+++ b/")
            continue

        if line.startswith("@@ "):
            if not flush_hunk():
                return None
            continue

        if current_path is not None and line[:1] in {" ", "+", "-"}:
            if line.startswith("--- "):
                continue

            hunk_lines.append(line)

    if not flush_hunk():
        return None

    diff_parts: list[str] = []

    for path, updated in patched_files.items():
        original = file_contents.get(path)

        if original is None or original == updated:
            continue

        diff_parts.extend(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    if not diff_parts:
        return None

    return "".join(diff_parts)


def apply_hunk_to_text(text: str, hunk_lines: list[str]) -> str | None:
    original_lines = text.splitlines(keepends=True)
    old_lines: list[str] = []
    new_lines: list[str] = []

    for line in hunk_lines:
        marker = line[0]
        content = line[1:] + "\n"

        if marker == " ":
            old_lines.append(content)
            new_lines.append(content)
        elif marker == "-":
            old_lines.append(content)
        elif marker == "+":
            new_lines.append(content)

    start = find_subsequence(original_lines, old_lines)

    if start is None:
        return None

    updated_lines = (
        original_lines[:start]
        + new_lines
        + original_lines[start + len(old_lines) :]
    )
    return "".join(updated_lines)


def find_subsequence(lines: list[str], sequence: list[str]) -> int | None:
    if not sequence:
        return None

    for index in range(len(lines) - len(sequence) + 1):
        if lines[index : index + len(sequence)] == sequence:
            return index

    return None


@app.command()
def version():
    """Show CodePilot version."""
    console.print("CodePilot CLI version 0.1.0")


@app.command()
def ask(
    question: str,
    max_turns: int = typer.Option(8, "--max-turns", min=1),
    tools_log: bool = typer.Option(True, "--tools-log/--no-tools-log"),
):
    """Ask an agentic question about the current repository."""
    console.print(Panel.fit(question, title="Your Question"))

    config = load_config()
    agent = CodePilotAgent(
        config=config,
        max_turns=max_turns,
        show_tool_calls=tools_log,
    )

    try:
        result = agent.run(question)
    except AgentRuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    console.print(Panel.fit(result.answer, title="CodePilot"))
    session_path = save_session(result.session)
    console.print(f"[dim]Session saved: {session_path}[/dim]")


@app.command()
def chat(
    max_turns: int = typer.Option(8, "--max-turns", min=1),
    tools_log: bool = typer.Option(True, "--tools-log/--no-tools-log"),
):
    """Start an interactive agent chat session."""
    console.print(Panel.fit("Welcome to CodePilot CLI", title="CodePilot"))

    config = load_config()
    agent = CodePilotAgent(
        config=config,
        max_turns=max_turns,
        show_tool_calls=tools_log,
    )

    while True:
        user_input = typer.prompt("You")

        if user_input.lower() in {"exit", "quit"}:
            console.print("Bye!")
            break

        try:
            result = agent.run(user_input)
        except AgentRuntimeError as e:
            console.print(f"[red]{e}[/red]")
            continue

        console.print(Panel.fit(result.answer, title="CodePilot"))
        session_path = save_session(result.session)
        console.print(f"[dim]Session saved: {session_path}[/dim]")


@app.command()
def files():
    """List project files."""
    project_files = list_project_files(".")

    table = Table(title="Project Files")
    table.add_column("#", justify="right")
    table.add_column("Path")

    for index, file_path in enumerate(project_files, start=1):
        table.add_row(str(index), file_path)

    console.print(table)


@app.command()
def read(path: str):
    """Read a project file."""
    try:
        content = read_text_file(path)
    except FileNotFoundError:
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=1)
    except IsADirectoryError:
        console.print(f"[red]Path is a directory:[/red] {path}")
        raise typer.Exit(code=1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    language = detect_language(path)
    syntax = Syntax(content, language, line_numbers=True, word_wrap=True)
    console.print(Panel.fit(path, title="File"))
    console.print(syntax)


@app.command("map")
def build_map():
    """Build a lightweight repo map."""
    repo_map = save_repo_map(".")

    table = Table(title="Repo Map")
    table.add_column("Path")
    table.add_column("Language")
    table.add_column("Symbols")

    for item in repo_map["files"]:
        symbols = ", ".join(item["symbols"][:5])
        if len(item["symbols"]) > 5:
            symbols += " ..."

        table.add_row(
            item["path"],
            item["language"],
            symbols,
        )

    console.print(table)
    console.print("[green]Repo map saved to .codepilot/repo_map.json[/green]")


@app.command()
def grep(query: str, limit: int = 20):
    """Search keyword in project files."""
    results = grep_search(query, max_results=limit)

    if not results:
        console.print(f"[yellow]No results found for:[/yellow] {query}")
        return

    table = Table(title=f"Search Results: {query}")
    table.add_column("#", justify="right")
    table.add_column("File")
    table.add_column("Line", justify="right")
    table.add_column("Content")

    for index, item in enumerate(results, start=1):
        table.add_row(
            str(index),
            item["path"],
            str(item["line"]),
            item["content"],
        )

    console.print(table)


@app.command()
def status():
    """Show git status."""
    result = git_status()
    console.print(Panel.fit(result, title="Git Status"))


@app.command()
def diff():
    """Show git diff."""
    result = git_diff()

    if result == "No unstaged diff.":
        console.print("[green]No unstaged diff.[/green]")
        return

    syntax = Syntax(result, "diff", line_numbers=True, word_wrap=True)
    console.print(Panel.fit("Current Git Diff", title="Diff"))
    console.print(syntax)


@app.command()
def test(command: str = typer.Argument("pytest")):
    """Run tests and show result."""
    console.print(f"[cyan]Running:[/cyan] {command}")

    try:
        result = run_tests(command)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    output = ""
    if result["stdout"]:
        output += result["stdout"]

    if result["stderr"]:
        output += "\n" + result["stderr"]

    if result["timed_out"]:
        console.print("[red]Test command timed out.[/red]")

    if result["returncode"] == 0:
        console.print("[green]Tests passed.[/green]")
    else:
        console.print("[red]Tests failed.[/red]")

    if output.strip():
        syntax = Syntax(output, "text", line_numbers=False, word_wrap=True)
        console.print(syntax)


@app.command()
def edit(
    instruction: str,
    test_command: str = typer.Option("pytest", "--test-command", "-t"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    retries: int = typer.Option(1, "--retries", min=0),
):
    """Generate a patch for a requested code change and apply it after confirmation."""
    config = load_config()
    prompt_path = Path(__file__).parent / "prompts" / "edit.md"
    edit_prompt = prompt_path.read_text(encoding="utf-8")

    try:
        context_result = collect_edit_context(instruction)
    except AgentRuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    read_files = context_result.session.get("read_files") or []

    if not read_files:
        console.print("[yellow]Could not determine relevant files to edit.[/yellow]")
        raise typer.Exit(code=1)

    file_contents = read_edit_files(read_files)

    if not file_contents:
        console.print("[yellow]Could not read any relevant files to edit.[/yellow]")
        raise typer.Exit(code=1)

    current_diff = git_diff()
    messages = build_edit_messages(
        edit_prompt=edit_prompt,
        instruction=instruction,
        file_contents=file_contents,
        current_diff=current_diff,
    )
    patch = ""
    check_result: dict | None = None

    for attempt in range(retries + 1):
        try:
            patch = normalize_patch(generate_patch(messages=messages, config=config))
        except LLMError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)

        if not patch:
            console.print("[yellow]No patch generated.[/yellow]")
            raise typer.Exit(code=1)

        check_result = apply_patch(
            patch,
            check=True,
            ignore_whitespace=True,
            recount=True,
        )

        if check_result["returncode"] == 0:
            break

        rebuilt_patch = rebuild_patch_from_contents(patch, file_contents)

        if rebuilt_patch:
            rebuilt_check_result = apply_patch(
                rebuilt_patch,
                check=True,
                ignore_whitespace=True,
                recount=True,
            )

            if rebuilt_check_result["returncode"] == 0:
                patch = rebuilt_patch
                check_result = rebuilt_check_result
                break

        if attempt >= retries:
            break

        console.print("[yellow]Patch check failed. Retrying...[/yellow]")
        messages = build_edit_messages(
            edit_prompt=edit_prompt,
            instruction=instruction,
            file_contents=file_contents,
            current_diff=current_diff,
            previous_patch=patch,
            patch_error=check_result["stderr"] or check_result["stdout"],
        )

    syntax = Syntax(patch, "diff", line_numbers=True, word_wrap=True)
    console.print(Panel.fit("Generated Patch", title="CodePilot Edit"))
    console.print(syntax)

    if check_result is None:
        check_result = apply_patch(
            patch,
            check=True,
            ignore_whitespace=True,
            recount=True,
        )

    changed_files = extract_changed_files(patch)
    session = {
        "session_id": create_session_id(),
        "question": instruction,
        "instruction": instruction,
        "messages": messages,
        "tool_steps": context_result.session.get("tool_steps", []),
        "edit_context_session": context_result.session,
        "read_files": list(file_contents.keys()),
        "changed_files": changed_files,
        "test_result": None,
        "patch_check_result": {
            "command": check_result["command"],
            "returncode": check_result["returncode"],
            "stdout": check_result["stdout"],
            "stderr": check_result["stderr"],
        },
    }

    if check_result["returncode"] != 0:
        console.print("[red]Patch failed git apply --check.[/red]")
        console.print(check_result["stderr"] or check_result["stdout"])
        save_session(session)
        raise typer.Exit(code=1)

    console.print("[green]Patch passed git apply --check.[/green]")

    if dry_run:
        save_session(session)
        console.print(f"Session: {session['session_id']}")
        return

    if not typer.confirm("Apply this patch?", default=False):
        console.print("[yellow]Patch not applied.[/yellow]")
        save_session(session)
        console.print(f"Session: {session['session_id']}")
        raise typer.Exit(code=1)

    apply_result = apply_patch(
        patch,
        ignore_whitespace=True,
        recount=True,
    )
    if apply_result["returncode"] != 0:
        console.print("[red]Patch apply failed.[/red]")
        console.print(apply_result["stderr"] or apply_result["stdout"])
        save_session(session)
        raise typer.Exit(code=1)

    try:
        test_result = run_tests(test_command)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        save_session(session)
        raise typer.Exit(code=1)
    session["test_result"] = {
        "command": test_result["command"],
        "returncode": test_result["returncode"],
        "timed_out": test_result["timed_out"],
    }
    save_session(session)

    if test_result["returncode"] == 0:
        console.print("[green]Patch applied and tests passed.[/green]")
    else:
        console.print("[red]Patch applied but tests failed.[/red]")

    console.print(f"Session: {session['session_id']}")


@app.command()
def history():
    """Show saved CodePilot sessions."""
    sessions = list_sessions(".")

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(title="Recent Sessions")
    table.add_column("Session ID")
    table.add_column("Question")
    table.add_column("Tool Steps", justify="right")
    table.add_column("Read Files", justify="right")

    for session in sessions:
        table.add_row(
            session["session_id"],
            session["question"],
            str(session.get("tool_steps_count", 0)),
            str(session.get("read_files_count", 0)),
        )

    console.print(table)


@app.command("show-session")
def show_session(session_id: str):
    """Show a saved CodePilot session trace."""
    try:
        session = load_session(session_id)
    except FileNotFoundError:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(code=1)

    console.print("[bold]Question:[/bold]")
    console.print(session.get("question", ""))

    console.print("\n[bold]Tool Steps:[/bold]")
    tool_steps = session.get("tool_steps") or []
    if not tool_steps:
        console.print("[dim]None[/dim]")
    else:
        for step in tool_steps:
            arguments = json.dumps(step.get("arguments") or {}, ensure_ascii=False)
            console.print(f"{step.get('step')}. {step.get('tool')} {arguments}")

    console.print("\n[bold]Read Files:[/bold]")
    read_files = session.get("read_files") or []
    if not read_files:
        console.print("[dim]None[/dim]")
    else:
        for path in read_files:
            console.print(f"- {path}")


@app.command()
def resume(session_id: str):
    """Show a saved CodePilot session."""
    try:
        session = load_session(session_id)
    except FileNotFoundError:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(code=1)

    syntax = Syntax(
        __import__("json").dumps(session, ensure_ascii=False, indent=2),
        "json",
        line_numbers=True,
        word_wrap=True,
    )
    console.print(syntax)


if __name__ == "__main__":
    app()
