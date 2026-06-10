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
codepilot ask "创建一个 notes.md" --allow-write
```

## Agent Loop

The agent uses a JSON-action loop. The model returns either a tool action or a
final answer, and CodePilot executes approved local tools before asking the
model to continue. Each tool call is printed as a numbered step:

```text
[Step 1] repo_map {}
[Step 2] read_file {"path": "pyproject.toml"}
[Step 3] read_file {"path": "codepilot/cli.py"}
```

`AgentContext` owns one agent run: messages, tool steps, files that were read,
tool output truncation, and final session export. The runtime limits max LLM
turns, repeated tool calls, and total file reads so a model cannot loop forever.

`codepilot ask` and `codepilot chat` are read-only by default. The write tools
`create_directory` and `write_file` are hidden and blocked unless you pass
`--allow-write`. File tools resolve paths inside the current project directory,
so `../` and project-external absolute paths are rejected. `write_file` also
refuses to overwrite existing files unless its `overwrite` argument is true.

## Development

Run the baseline checks:

```bash
python -m compileall codepilot
pytest
```
