import subprocess


def run_command(command: str, timeout: int = 60) -> dict:
    """
    Run a shell command with timeout.
    """
    try:
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        return {
            "command": command,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "timed_out": False,
        }

    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "returncode": -1,
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
            "timed_out": True,
        }


def run_tests(command: str = "pytest") -> dict:
    """
    Run project tests.
    """
    return run_command(command)
