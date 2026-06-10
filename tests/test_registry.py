from codepilot.tools import registry


def test_no_argument_tool_ignores_extra_arguments(monkeypatch):
    monkeypatch.setitem(
        registry.TOOL_HANDLERS,
        "repo_map",
        lambda: "repo map",
    )

    result = registry.execute_tool(
        "repo_map",
        '{"description": "Build repo map to understand project structure"}',
    )

    assert result == "repo map"


def test_execute_tool_action_rejects_write_tools_without_permission():
    result = registry.execute_tool_action(
        "write_file",
        {"path": "notes.txt", "content": "hello\n"},
    )

    assert result.success is False
    assert "without write permission" in (result.error or "")


def test_format_tools_for_prompt_hides_write_tools_by_default():
    prompt = registry.format_tools_for_prompt()

    assert "write_file" not in prompt
    assert "create_directory" not in prompt


def test_execute_tool_action_rejects_write_tools_without_allow_write():
    result = registry.execute_tool_action(
        "create_directory",
        {"path": "examples"},
    )

    assert result.success is False
    assert "without write permission" in (result.error or "")


def test_execute_tool_action_allows_write_tools_with_allow_write(monkeypatch):
    monkeypatch.setitem(
        registry.TOOL_HANDLERS,
        "write_file",
        lambda path, content, overwrite=False: f"{path}:{content}:{overwrite}",
    )

    result = registry.execute_tool_action(
        "write_file",
        {"path": "notes.txt", "content": "hello\n", "overwrite": True},
        allow_write=True,
    )

    assert result.success is True
    assert result.content == "notes.txt:hello\n:True"


def test_execute_tool_rejects_write_tools_without_permission():
    result = registry.execute_tool(
        "write_file",
        '{"path": "notes.txt", "content": "hello\\n"}',
    )

    assert "without write permission" in result
