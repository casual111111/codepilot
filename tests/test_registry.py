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
