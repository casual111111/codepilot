from pathlib import Path

import pytest

from codepilot.tools.filesystem import list_project_files, read_text_file


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

    content = read_text_file(str(target), max_chars=3)

    assert content.startswith("abc")
    assert "[Content truncated" in content


def test_read_text_file_rejects_directories(tmp_path: Path):
    with pytest.raises(IsADirectoryError):
        read_text_file(str(tmp_path))
