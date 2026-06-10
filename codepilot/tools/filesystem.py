from pathlib import Path


IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "dist",
    "build",
    ".codepilot",
}

ALLOWED_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
}

ALLOWED_FILENAMES = {
    ".env.example",
    ".gitignore",
}


def list_project_files(root: str = ".") -> list[str]:
    """
    Recursively list project files under root.
    Returns relative paths using '/' as separator.
    """
    #获取绝对路径
    root_path = Path(root).resolve()
    files: list[str] = []

    for path in root_path.rglob("*"):
        #不保存目录
        if not path.is_file():
            continue

        relative_path = path.relative_to(root_path)

        if any(
            part in IGNORE_DIRS or part.endswith(".egg-info")
            for part in relative_path.parts
        ):
            continue

        if path.suffix not in ALLOWED_SUFFIXES and path.name not in ALLOWED_FILENAMES:
            continue

        files.append(relative_path.as_posix())

    return sorted(files)


def read_text_file(path: str, max_chars: int = 12000) -> str:
    """
    Read a text file with a character limit.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {path}")

    content = file_path.read_text(encoding="utf-8", errors="replace")

    if len(content) > max_chars:
        return (
            content[:max_chars]
            + f"\n\n[Content truncated: showing first {max_chars} characters]"
        )

    return content
