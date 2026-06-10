# CodePilot CLI

CodePilot is a lightweight coding-agent CLI for inspecting a local repository.
It can list files, read source, build a small repo map, grep text, run tests, and
ask an LLM-backed agent questions about the project.

## Install

```bash
pip install -e .
```

Create a `.env` file if you want to use `codepilot ask` or `codepilot chat`:

```bash
CODEPILOT_API_KEY=your-api-key
CODEPILOT_BASE_URL=https://api.openai.com/v1
CODEPILOT_MODEL=gpt-4o-mini
```

## Commands

```bash
codepilot --help
codepilot files
codepilot read codepilot/cli.py
codepilot map
codepilot grep "Typer"
codepilot test "python -m compileall codepilot"
codepilot ask "这个项目入口在哪里？"
codepilot ask "这个项目入口在哪里？" --max-turns 6 --no-tools-log
```

## Agent Loop

The agent uses OpenAI-compatible tool calls to inspect the repository before
answering. Each tool call is printed as a numbered step:

```text
[Step 1] repo_map {}
[Step 2] read_file {"path": "pyproject.toml"}
[Step 3] read_file {"path": "codepilot/cli.py"}
```

`AgentContext` owns one agent run: messages, tool steps, files that were read,
tool output truncation, and final session export. The runtime limits max LLM
turns, repeated tool calls, and total file reads so a model cannot loop forever.

## Development

Run the baseline checks:

```bash
python -m compileall codepilot
pytest
```
