from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from codepilot.repo_map import save_repo_map
from codepilot.tools.git import git_diff, git_status
from codepilot.tools.filesystem import list_project_files, read_text_file
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
def ask(question: str):
    """Ask a one-shot question."""
    console.print(Panel.fit(question, title="Your Question"))
    console.print("CodePilot: LLM is not connected yet.")


@app.command()
def chat():
    """Start an interactive chat session."""
    console.print(Panel.fit("Welcome to CodePilot CLI", title="CodePilot"))

    while True:
        user_input = typer.prompt("You")

        if user_input.lower() in {"exit", "quit"}:
            console.print("Bye!")
            break

        console.print(f"CodePilot: You said: {user_input}")


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


if __name__ == "__main__":
    app()
