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


def test_execute_tool_rejects_write_tools_without_permission():
    result = registry.execute_tool(
        "write_file",
        '{"path": "notes.txt", "content": "hello\\n"}',
    )

    assert "without write permission" in result
