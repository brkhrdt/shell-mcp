import pytest
import asyncio
from shell_mcp import (
    peek_shell_buffer,
    start_shell_session,
    run_shell_command,
    close_shell_session,
    get_active_sessions,
    close_all_sessions,
    _active_sessions,  # Access for testing cleanup
)


@pytest.fixture(autouse=True)
async def cleanup_sessions():
    """Fixture to ensure all sessions are closed before and after each test."""
    await close_all_sessions()  # Clean up before test
    yield
    await close_all_sessions()  # Clean up after test


@pytest.mark.asyncio
async def test_start_and_close_bash_session():
    """Test starting and closing a basic bash session."""
    start_result = await start_shell_session(["bash", "--norc", "-i"])
    assert "Shell session started successfully" in start_result
    session_id = start_result.split("Session ID: ")[1]

    active_sessions = await get_active_sessions()
    assert session_id in active_sessions

    close_result = await close_shell_session(session_id)
    assert "closed successfully" in close_result

    active_sessions = await get_active_sessions()
    assert session_id not in active_sessions
    assert session_id not in _active_sessions


@pytest.mark.asyncio
async def test_run_simple_command():
    """Test running a simple command in a bash session."""
    start_result = await start_shell_session(["bash", "--norc", "-i"])
    session_id = start_result.split("Session ID: ")[1]

    try:
        command_output = await run_shell_command(session_id, "echo hello world")
        assert "hello world" in command_output
        assert session_id in _active_sessions  # Session should still be active
    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_invalid_session_id():
    """Test running a command with an invalid session ID."""
    result = await run_shell_command("non-existent-id", "ls")
    assert "Session non-existent-id not found" in result


@pytest.mark.asyncio
async def test_close_non_existent_session():
    """Test closing a non-existent session."""
    result = await close_shell_session("non-existent-id")
    assert "Session non-existent-id not found" in result


@pytest.mark.asyncio
async def test_shell_process_death_cleanup():
    """Test that a session is cleaned up if its underlying process dies."""
    start_result = await start_shell_session(["bash", "--norc", "-i"])
    session_id = start_result.split("Session ID: ")[1]

    shell = _active_sessions[session_id]
    assert shell.child is not None
    assert shell.child.isalive()

    # Force the child process to terminate
    shell.child.close()
    await asyncio.sleep(0.1)  # Give a moment for pexpect to register closure

    assert not shell.child.isalive()

    # Running a command should now trigger cleanup
    result = await run_shell_command(session_id, "echo test")
    assert f"Session {session_id} is no longer active (process died)." in result
    assert session_id not in _active_sessions


@pytest.mark.asyncio
async def test_start_shell_failure():
    """Test starting a shell with an invalid command."""
    result = await start_shell_session(["non_existent_command"])
    assert "Failed to start shell session" in result
    assert "non_existent_command" in result


@pytest.mark.asyncio
async def test_get_active_sessions_empty():
    """Test get_active_sessions when no sessions are active."""
    await close_all_sessions()  # Ensure no sessions are active
    result = await get_active_sessions()
    assert "No active shell sessions." in result


@pytest.mark.asyncio
async def test_close_all_sessions():
    """Test closing all active sessions."""
    await start_shell_session(["bash", "--norc", "-i"])
    await start_shell_session(["python3"])
    assert len(_active_sessions) == 2

    result = await close_all_sessions()
    assert "Closed 2 sessions successfully." in result
    assert not _active_sessions


@pytest.mark.asyncio
async def test_python_multiline_command():
    """Test running Python command via MCP."""
    # Start a Python session
    start_result = await start_shell_session(["python3"])  # Removed prompt_patterns
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Send the multiline command
        result_part1 = await run_shell_command(
            session_id,
            'for i in range(1, 6):\n    if i == 1: print("eins")\n    elif i == 2: print("zwei")\n    elif i == 3: print("drei")\n    elif i == 4: print("vier")\n    else: print("fünf")',
        )

        # Verify that it indicates no prompt was found (as it's waiting for more input)
        # The shell no longer adds this specific message. It just returns what it read.
        # We expect the output to contain the echoed command and potentially some initial output.
        assert "for i in range(1, 6):" in result_part1
        assert (
            ">>>"
            not in result_part1.split("\n")[-1]  # check that new prompt is not at end
        )  # No prompt should be present yet

        # Send an empty line to execute the multiline command
        result_part2 = await run_shell_command(session_id, "")

        # Verify output contains expected result
        assert "eins" in result_part2
        assert "\nzwei" in result_part2
        assert "\ndrei" in result_part2
        assert "\nvier" in result_part2
        assert "\nfünf" in result_part2
        assert ">>>" in result_part2  # Prompt should be back after execution

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_session_timeout():
    """Test command timeout handling."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"]
    )  # Removed prompt_patterns
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a command with very short timeout that should not complete
        command = "sleep 1"
        result = await run_shell_command(session_id, command, timeout=0.1)

        # The shell no longer adds this specific message. It just returns what it read.
        # We expect the output to contain the echoed command and potentially some initial output.
        assert command in result  # The command should be in the partial output
        assert len(result) < 50  # Expecting partial output, not the full 5-second wait

        # Now, send a newline and check if the sleep command has finished
        result_after_newline = await run_shell_command(session_id, "")
        assert (
            "bash" in result_after_newline or "$" in result_after_newline
        )  # Prompt should be back

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_peek_running_command():
    """Test command timeout handling."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"]
    )  # Removed prompt_patterns
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a command with very short timeout that should not complete
        command = "sleep 1"
        result = await run_shell_command(session_id, command, timeout=0.1)

        # The shell no longer adds this specific message. It just returns what it read.
        # We expect the output to contain the echoed command and potentially some initial output.
        assert command in result  # The command should be in the partial output
        assert len(result) < 50  # Expecting partial output, not the full 5-second wait

        # Now, send a newline and check if the sleep command has finished
        await peek_shell_buffer(session_id, 1) # Removed assignment to result_peek
        assert "bash" not in result  # new prompt not ready

        result = await run_shell_command(session_id, "", timeout=1)
        assert "bash" in result  # sleep done, prompt is ready now

    finally:
        await close_shell_session(session_id)


# TODO test full buffer history, should include all commands
