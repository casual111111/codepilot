import ast
import json
from pathlib import Path
from typing import Any

from codepilot.tools.filesystem import list_project_files, read_text_file


def detect_language(path: str) -> str:
    suffix = Path(path).suffix.lower()

    if suffix == ".py":
        return "python"
    if suffix == ".md":
        return "markdown"
    if suffix == ".json":
        return "json"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yaml", ".yml"}:
        return "yaml"

    return "text"


def extract_python_symbols(path: str) -> list[str]:
    content = read_text_file(path)
    tree = ast.parse(content)

    symbols: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            symbols.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append(node.name)
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    symbols.append(f"{node.name}.{item.name}")
                elif isinstance(item, ast.AsyncFunctionDef):
                    symbols.append(f"{node.name}.{item.name}")

    return symbols


def build_repo_map(root: str = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    project_files = list_project_files(root)

    files: list[dict[str, Any]] = []

    for file_path in project_files:
        abs_path = root_path / file_path
        language = detect_language(file_path)

        item: dict[str, Any] = {
            "path": file_path,
            "language": language,
            "size": abs_path.stat().st_size,
            "symbols": [],
        }

        if language == "python":
            try:
                item["symbols"] = extract_python_symbols(str(abs_path))
            except SyntaxError:
                item["symbols"] = ["<syntax error>"]

        files.append(item)

    return {
        "root": str(root_path),
        "file_count": len(files),
        "files": files,
    }


def save_repo_map(
    root: str = ".",
    output_path: str = ".codepilot/repo_map.json",
) -> dict[str, Any]:
    repo_map = build_repo_map(root)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(repo_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return repo_map


def load_repo_map(path: str = ".codepilot/repo_map.json") -> dict[str, Any]:
    repo_map_path = Path(path)

    if not repo_map_path.exists():
        raise FileNotFoundError(f"Repo map not found: {path}")

    return json.loads(repo_map_path.read_text(encoding="utf-8"))
