from pathlib import Path

import pytest

from codepilot.tools.filesystem import (
    create_directory,
    list_project_files,
    read_text_file,
    write_text_file,
)


def test_list_project_files_skips_runtime_dirs(tmp_path: Path):
    (tmp_path / "codepilot").mkdir()
    (tmp_path / "codepilot" / "cli.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".codepilot").mkdir()
    (tmp_path / ".codepilot" / "repo_map.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.bin").write_bytes(b"\x00\x01")

    assert list_project_files(str(tmp_path)) == ["codepilot/cli.py"]


def test_read_text_file_truncates_content(tmp_path: Path):
    target = tmp_path / "long.txt"
    target.write_text("abcdef", encoding="utf-8")

    content = read_text_file("long.txt", root=str(tmp_path), max_chars=3)

    assert content.startswith("abc")
    assert "[Content truncated" in content


def test_read_text_file_rejects_directories(tmp_path: Path):
    with pytest.raises(IsADirectoryError):
        read_text_file(".", root=str(tmp_path))


def test_read_text_file_rejects_paths_outside_project(tmp_path: Path):
    with pytest.raises(ValueError):
        read_text_file("../outside.txt", root=str(tmp_path))


def test_write_text_file_creates_parent_directories(tmp_path: Path):
    write_text_file("examples/bubble_sort.py", "print('ok')\n", root=str(tmp_path))

    assert (tmp_path / "examples" / "bubble_sort.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_write_text_file_rejects_paths_outside_project(tmp_path: Path):
    with pytest.raises(ValueError):
        write_text_file("../outside.txt", "nope\n", root=str(tmp_path))


def test_write_text_file_refuses_overwrite_by_default(tmp_path: Path):
    target = tmp_path / "exists.txt"
    target.write_text("old\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_text_file("exists.txt", "new\n", root=str(tmp_path))

    assert target.read_text(encoding="utf-8") == "old\n"


def test_write_text_file_allows_overwrite_when_true(tmp_path: Path):
    target = tmp_path / "exists.txt"
    target.write_text("old\n", encoding="utf-8")

    write_text_file("exists.txt", "new\n", root=str(tmp_path), overwrite=True)

    assert target.read_text(encoding="utf-8") == "new\n"


def test_create_directory_rejects_paths_outside_project(tmp_path: Path):
    with pytest.raises(ValueError):
        create_directory("../outside", root=str(tmp_path))
