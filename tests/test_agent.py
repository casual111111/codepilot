from codepilot.agent import CodePilotAgent
from codepilot.config import CodePilotConfig


def test_agent_executes_tool_call_and_returns_final_answer(monkeypatch, capsys):
    responses = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "pyproject.toml"}',
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "Entry point is codepilot.cli:app.",
        },
    ]

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)
    monkeypatch.setattr(
        "codepilot.agent.execute_tool",
        lambda name, args: "codepilot = 'codepilot.cli:app'",
    )

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
    )

    answer = agent.run("entry?")

    assert answer == "Entry point is codepilot.cli:app."
    assert "[Step 1] read_file" in capsys.readouterr().out
    assert agent.last_context is not None
    assert agent.last_context.tool_steps[0]["name"] == "read_file"


def test_agent_limits_repeated_repo_map_calls(monkeypatch):
    responses = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "one",
                    "type": "function",
                    "function": {"name": "repo_map", "arguments": "{}"},
                },
                {
                    "id": "two",
                    "type": "function",
                    "function": {"name": "repo_map", "arguments": "{}"},
                },
            ],
        },
        {"role": "assistant", "content": "done"},
    ]
    executed = []

    def fake_chat_completion(**kwargs):
        return responses.pop(0)

    def fake_execute_tool(name, args):
        executed.append(name)
        return "map"

    monkeypatch.setattr("codepilot.agent.chat_completion", fake_chat_completion)
    monkeypatch.setattr("codepilot.agent.execute_tool", fake_execute_tool)

    agent = CodePilotAgent(
        config=CodePilotConfig(api_key="test", base_url="http://test", model="test"),
        max_tool_calls_per_name={"repo_map": 1},
        show_tool_calls=False,
    )

    assert agent.run("map?") == "done"
    assert executed == ["repo_map"]
