from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from codepilot.tools.filesystem import list_project_files, read_text_file

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


if __name__ == "__main__":
    app()
