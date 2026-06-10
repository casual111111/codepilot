from codepilot.agent_context import AgentContext


def test_agent_context_records_read_files_and_truncates_tool_output():
    context = AgentContext(
        user_question="Where is the entrypoint?",
        max_tool_output_chars=5,
    )

    result = context.truncate_tool_output("abcdef")
    step = context.add_tool_step(
        name="read_file",
        arguments='{"path": "codepilot/cli.py"}',
        result=result,
        success=True,
    )

    assert result.startswith("abcde")
    assert "[Tool output truncated" in result
    assert context.read_files == {"codepilot/cli.py"}
    assert step == 1
    assert context.tool_steps[0]["tool"] == "read_file"
    assert context.tool_steps[0]["arguments"] == {"path": "codepilot/cli.py"}
    assert context.tool_steps[0]["success"] is True


def test_agent_context_compacts_messages_keeps_system_prompt():
    context = AgentContext(user_question="hello", max_messages=3)

    for index in range(10):
        context.add_assistant_message({"role": "assistant", "content": str(index)})

    assert context.messages[0]["role"] == "system"
    assert len(context.messages) == 4
    assert context.messages[-1]["content"] == "9"


def test_agent_context_builds_session_record():
    context = AgentContext(user_question="change it")
    context.add_tool_step(
        name="read_file",
        arguments='{"path": "codepilot/cli.py"}',
        result="content",
        success=True,
    )

    record = context.to_session_dict(
        session_id="20260610-001",
        changed_files=["codepilot/cli.py"],
        test_result={"returncode": 0},
    )

    assert record["question"] == "change it"
    assert record["read_files"] == ["codepilot/cli.py"]
    assert record["changed_files"] == ["codepilot/cli.py"]
    assert record["test_result"] == {"returncode": 0}
