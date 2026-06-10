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
```

## Agent Loop

The agent uses OpenAI-compatible tool calls to inspect the repository before
answering. Each tool call is printed as a numbered step:

```text
[1] tool_call: repo_map {}
[2] tool_call: read_file {"path": "pyproject.toml"}
[3] tool_call: read_file {"path": "codepilot/cli.py"}
```

The context layer tracks messages, tool steps, files that were read, and
truncates long tool output before it is sent back to the model.

## Development

Run the baseline checks:

```bash
python -m compileall codepilot
pytest
```
