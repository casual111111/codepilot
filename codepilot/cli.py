from pathlib import Path
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from codepilot.agent import AgentRuntimeError, CodePilotAgent
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

    result = run_tests(command)

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
):
    """Generate a patch for a requested code change and apply it after confirmation."""
    config = load_config()
    prompt_path = Path(__file__).parent / "prompts" / "edit.md"
    edit_prompt = prompt_path.read_text(encoding="utf-8")
    repo_map = save_repo_map(".")
    current_diff = git_diff()

    messages = [
        {"role": "system", "content": edit_prompt},
        {
            "role": "user",
            "content": (
                f"User request:\n{instruction}\n\n"
                f"Repo map:\n{repo_map}\n\n"
                f"Current unstaged diff:\n{current_diff}\n"
            ),
        },
    ]

    try:
        patch = generate_patch(messages=messages, config=config)
    except LLMError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    patch = patch.strip()

    if not patch:
        console.print("[yellow]No patch generated.[/yellow]")
        raise typer.Exit(code=1)

    syntax = Syntax(patch, "diff", line_numbers=True, word_wrap=True)
    console.print(Panel.fit("Generated Patch", title="CodePilot Edit"))
    console.print(syntax)

    check_result = apply_patch(patch, check=True)
    if check_result["returncode"] != 0:
        console.print("[red]Patch failed git apply --check.[/red]")
        console.print(check_result["stderr"] or check_result["stdout"])
        raise typer.Exit(code=1)

    if not typer.confirm("Apply this patch?", default=False):
        console.print("[yellow]Patch not applied.[/yellow]")
        raise typer.Exit(code=1)

    apply_result = apply_patch(patch)
    if apply_result["returncode"] != 0:
        console.print("[red]Patch apply failed.[/red]")
        console.print(apply_result["stderr"] or apply_result["stdout"])
        raise typer.Exit(code=1)

    test_result = run_tests(test_command)
    changed_files = extract_changed_files(patch)
    session = {
        "session_id": create_session_id(),
        "question": instruction,
        "messages": messages,
        "tool_steps": [],
        "read_files": [],
        "changed_files": changed_files,
        "test_result": {
            "command": test_result["command"],
            "returncode": test_result["returncode"],
            "timed_out": test_result["timed_out"],
        },
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
