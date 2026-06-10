import subprocess

from codepilot.config import CodePilotConfig
from codepilot.llm import chat_text


def generate_patch(messages: list[dict], config: CodePilotConfig) -> str:
    return chat_text(messages=messages, config=config).strip()


def apply_unified_diff(
    diff: str,
    check: bool = False,
    ignore_space_change: bool = False,
    ignore_whitespace: bool = False,
    recount: bool = False,
) -> dict:
    command = ["git", "apply"]

    if check:
        command.append("--check")

    if ignore_space_change:
        command.append("--ignore-space-change")

    if ignore_whitespace:
        command.append("--ignore-whitespace")

    if recount:
        command.append("--recount")

    process = subprocess.run(
        command,
        input=diff,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return {
        "command": " ".join(command),
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def apply_patch(
    diff: str,
    check: bool = False,
    ignore_space_change: bool = False,
    ignore_whitespace: bool = False,
    recount: bool = False,
) -> dict:
    return apply_unified_diff(
        diff,
        check=check,
        ignore_space_change=ignore_space_change,
        ignore_whitespace=ignore_whitespace,
        recount=recount,
    )


def extract_changed_files(diff: str) -> list[str]:
    files: list[str] = []

    for line in diff.splitlines():
        if not line.startswith("+++ b/"):
            continue

        path = line.removeprefix("+++ b/")
        if path != "/dev/null":
            files.append(path)

    return files
