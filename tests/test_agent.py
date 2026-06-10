from codepilot.agent import CodePilotAgent
from codepilot.config import CodePilotConfig
from codepilot.tools.registry import ToolResult


def test_agent_executes_tool_action_and_returns_final_answer(monkeypatch, capsys):
    responses = [
        {
            "role": "assistant",
            "content": (
                '{"action":"tool","tool_name":"read_file",'
                '"arguments":{"path":"pyproject.toml"}}'
            ),
        },
        {
            "role": "assistant",
            "content": (
                '{"action":"final","answer":"Entry point is codepilot.cli:app."}'
            ),
        },
    ]

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    def fake_execute_tool_action(name, arguments, allow_write=False):
        assert name == "read_file"
        assert arguments == {"path": "pyproject.toml"}
        assert allow_write is False
        return ToolResult(success=True, content="codepilot = 'codepilot.cli:app'")

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)
    monkeypatch.setattr(
        "codepilot.agent.execute_tool_action",
        fake_execute_tool_action,
    )

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
    )

    result = agent.run("entry?")

    assert result.answer == "Entry point is codepilot.cli:app."
    assert result.session["question"] == "entry?"
    assert result.session["read_files"] == ["pyproject.toml"]
    assert "[Step 1] read_file" in capsys.readouterr().out
    assert agent.last_context is not None
    assert agent.last_context.tool_steps[0]["tool"] == "read_file"
    assert agent.last_context.tool_steps[0]["success"] is True


def test_agent_limits_repeated_repo_map_calls(monkeypatch):
    responses = [
        {
            "role": "assistant",
            "content": '{"action":"tool","tool_name":"repo_map","arguments":{}}',
        },
        {
            "role": "assistant",
            "content": '{"action":"tool","tool_name":"repo_map","arguments":{}}',
        },
        {"role": "assistant", "content": '{"action":"final","answer":"done"}'},
    ]
    executed = []

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    def fake_execute_tool_action(name, arguments, allow_write=False):
        assert allow_write is False
        executed.append(name)
        return ToolResult(success=True, content="map")

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)
    monkeypatch.setattr("codepilot.agent.execute_tool_action", fake_execute_tool_action)

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        max_tool_calls_per_name={"repo_map": 1},
        show_tool_calls=False,
    )

    assert agent.run("map?").answer == "done"
    assert executed == ["repo_map"]
    assert agent.last_context is not None
    assert agent.last_context.tool_steps[1]["success"] is False


def test_agent_limits_read_file_calls_per_run(monkeypatch):
    responses = [
        {
            "role": "assistant",
            "content": (
                '{"action":"tool","tool_name":"read_file",'
                '"arguments":{"path":"one.py"}}'
            ),
        },
        {
            "role": "assistant",
            "content": (
                '{"action":"tool","tool_name":"read_file",'
                '"arguments":{"path":"two.py"}}'
            ),
        },
        {"role": "assistant", "content": '{"action":"final","answer":"done"}'},
    ]
    executed = []

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    def fake_execute_tool_action(name, arguments, allow_write=False):
        assert allow_write is False
        executed.append(arguments)
        return ToolResult(success=True, content="content")

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)
    monkeypatch.setattr("codepilot.agent.execute_tool_action", fake_execute_tool_action)

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        max_read_file_per_run=1,
        show_tool_calls=False,
    )

    result = agent.run("read?")

    assert result.answer == "done"
    assert executed == [{"path": "one.py"}]
    assert result.session["read_files"] == ["one.py"]
    assert agent.last_context is not None
    assert agent.last_context.tool_steps[1]["success"] is False


def test_agent_recovers_from_invalid_json_response(monkeypatch):
    responses = [
        {"role": "assistant", "content": "not json"},
        {"role": "assistant", "content": '{"action":"final","answer":"done"}'},
    ]

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        show_tool_calls=False,
    )

    result = agent.run("hello")

    assert result.answer == "done"
    assert result.session["tool_steps"] == []


def test_agent_remembers_previous_chat_turn(monkeypatch):
    captured_messages = []
    responses = [
        {"role": "assistant", "content": '{"action":"final","answer":"first answer"}'},
        {"role": "assistant", "content": '{"action":"final","answer":"second answer"}'},
    ]

    def fake_chat_completion(**kwargs):
        captured_messages.append(kwargs["messages"])
        return responses.pop(0)

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        show_tool_calls=False,
    )

    assert agent.run("first question").answer == "first answer"
    assert agent.run("what did I ask before?").answer == "second answer"

    second_turn_content = "\n".join(
        message["content"] for message in captured_messages[1]
    )
    assert "first question" in second_turn_content
    assert "first answer" in second_turn_content


def test_agent_hides_write_tools_by_default():
    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        show_tool_calls=False,
    )

    assert "write_file" not in agent.tools_prompt
    assert "create_directory" not in agent.tools_prompt


def test_agent_allows_write_tools_when_enabled():
    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        show_tool_calls=False,
        allow_write=True,
    )

    assert "write_file" in agent.tools_prompt
    assert "create_directory" in agent.tools_prompt
    assert agent.max_tool_calls_per_name["write_file"] == 5
    assert agent.max_tool_calls_per_name["create_directory"] == 3
