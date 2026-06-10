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
    root_path = Path(root).resolve()
    files: list[str] = []

    for path in root_path.rglob("*"):
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


def resolve_project_path(path: str, root: str = ".") -> Path:
    """
    Resolve a user path and ensure it stays inside the project root.
    """
    root_path = Path(root).resolve()
    target_path = (root_path / path).resolve()

    if target_path != root_path and root_path not in target_path.parents:
        raise ValueError(f"Path is outside project root: {path}")

    return target_path


def create_directory(path: str, root: str = ".") -> str:
    """
    Create a directory inside the project root.
    """
    target_path = resolve_project_path(path, root=root)
    target_path.mkdir(parents=True, exist_ok=True)
    return f"Directory created: {Path(path).as_posix()}"


def write_text_file(path: str, content: str, root: str = ".") -> str:
    """
    Write a UTF-8 text file inside the project root, creating parent directories.
    """
    target_path = resolve_project_path(path, root=root)

    if target_path.exists() and target_path.is_dir():
        raise IsADirectoryError(f"Path is a directory: {path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return f"File written: {Path(path).as_posix()}"
