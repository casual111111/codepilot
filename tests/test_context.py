from codepilot.context import AgentContext


def test_agent_context_records_read_files_and_truncates_tool_output():
    context = AgentContext(
        user_question="Where is the entrypoint?",
        max_tool_output_chars=5,
    )

    result = context.record_tool_call(
        step=1,
        name="read_file",
        arguments='{"path": "codepilot/cli.py"}',
        result="abcdef",
    )

    assert result.startswith("abcde")
    assert "[Tool output truncated" in result
    assert context.read_files == {"codepilot/cli.py"}
    assert context.tool_steps[0]["name"] == "read_file"


def test_agent_context_compacts_messages_keeps_system_prompt():
    context = AgentContext(user_question="hello", max_messages=3)

    for index in range(10):
        context.append_message({"role": "assistant", "content": str(index)})

    assert context.messages[0]["role"] == "system"
    assert len(context.messages) == 4
    assert context.messages[-1]["content"] == "9"
