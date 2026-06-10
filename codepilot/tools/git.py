import subprocess


def run_git_command(args: list[str]) -> tuple[int, str, str]:
    """
    Run a git command and return:
    - returncode
    - stdout
    - stderr
    """
    process = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return process.returncode, process.stdout, process.stderr


def git_status() -> str:
    code, stdout, stderr = run_git_command(["status", "--short"])

    if code != 0:
        return stderr.strip() or "Git status failed."

    if not stdout.strip():
        return "Working tree clean."

    return stdout.strip()


def git_diff() -> str:
    code, stdout, stderr = run_git_command(["diff"])

    if code != 0:
        return stderr.strip() or "Git diff failed."

    if not stdout.strip():
        return "No unstaged diff."

    return stdout


def git_diff_cached() -> str:
    code, stdout, stderr = run_git_command(["diff", "--cached"])

    if code != 0:
        return stderr.strip() or "Git cached diff failed."

    if not stdout.strip():
        return "No staged diff."

    return stdout
