import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="codepilot",
    help="CodePilot CLI - A lightweight coding agent for local repositories.",
)

console = Console()


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
