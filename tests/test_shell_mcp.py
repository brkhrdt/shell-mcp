import pytest
import asyncio
import pytest_asyncio
from unittest.mock import patch, MagicMock
from shell_mcp import (
    start_shell_session,
    get_active_sessions,
    run_shell_command,
    close_shell_session,
    close_all_sessions,
    _active_sessions,
)


# Fixture to clean up sessions after each test
@pytest_asyncio.fixture
async def cleanup_sessions():
    """Clean up all sessions before and after each test."""
    # Clear sessions before test
    _active_sessions.clear()
    yield
    # Clean up sessions after test
    await close_all_sessions()


@pytest.mark.asyncio
async def test_start_and_close_shell_session():
    """Test that shell session can be started and closed properly via MCP."""
    # Start a bash session
    result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )

    # Verify session started successfully
    assert "Shell session started successfully" in result
    assert "Session ID:" in result

    # Extract session ID from result
    session_id = result.split("Session ID: ")[1]

    # Verify session is in active sessions
    sessions_info = await get_active_sessions()
    assert session_id in sessions_info
    assert "bash" in sessions_info
    assert "alive" in sessions_info

    # Close the session
    close_result = await close_shell_session(session_id)
    assert "closed successfully" in close_result

    # Verify session is no longer active
    sessions_info = await get_active_sessions()
    assert "No active shell sessions" in sessions_info


@pytest.mark.asyncio
async def test_start_shell_session_failure():
    """Test that shell properly handles failed process start via MCP."""
    # Try to start with nonexistent command
    result = await start_shell_session(
        ["nonexistent_command_12345"], prompt_patterns=[r"bash.*\$"]
    )

    # Verify failure is reported
    assert "Failed to start shell session" in result

    # Verify no sessions are active
    sessions_info = await get_active_sessions()
    assert "No active shell sessions" in sessions_info


@pytest.mark.asyncio
async def test_run_shell_command():
    """Test running a simple command in the shell via MCP."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a simple command
        result = await run_shell_command(session_id, "echo 'hello world'")

        # Verify output contains expected content
        assert "hello world" in result

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_run_multiple_commands():
    """Test running multiple commands sequentially via MCP."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run first command
        result1 = await run_shell_command(session_id, "echo 'first'")
        assert "first" in result1

        # Run second command
        result2 = await run_shell_command(session_id, "echo 'second'")
        assert "second" in result2

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_shell_with_working_directory():
    """Test shell with specific working directory via MCP."""
    # Start a bash session with specific working directory
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], cwd="/tmp", prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a command that depends on current directory
        result = await run_shell_command(session_id, "pwd")
        assert "/tmp" in result

        # Verify session info shows correct working directory
        sessions_info = await get_active_sessions()
        assert "cwd: /tmp" in sessions_info

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_run_command_nonexistent_session():
    """Test error handling when trying to run command in nonexistent session."""
    # Try to run command in nonexistent session
    result = await run_shell_command("nonexistent-session-id", "echo test")

    # Verify error message
    assert "Session nonexistent-session-id not found" in result
    assert "Use get_active_sessions()" in result


@pytest.mark.asyncio
async def test_close_nonexistent_session():
    """Test error handling when trying to close nonexistent session."""
    # Try to close nonexistent session
    result = await close_shell_session("nonexistent-session-id")

    # Verify error message
    assert "Session nonexistent-session-id not found" in result


@pytest.mark.asyncio
async def test_complex_command():
    """Test running a more complex command via MCP."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a command that produces multi-line output
        result = await run_shell_command(session_id, "ls -la")

        # Should contain some output
        assert len(result) > 0
        # Check that the second line starts with 'd' and ends with '.'
        lines = result.split("\n")
        line = lines[2].strip()
        dot_line_found = line.startswith("d") and line.endswith(".")
        assert dot_line_found

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_tclsh_command():
    """Test running TCL command via MCP."""
    # Start a TCL session
    start_result = await start_shell_session(["tclsh"], prompt_patterns=[r"%"])
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run the TCL expression
        result = await run_shell_command(session_id, "expr 2+3")

        # Verify output contains expected result
        assert "5" in result

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_python_command():
    """Test running Python command via MCP."""
    # Start a Python session
    start_result = await start_shell_session(["python"], prompt_patterns=[r"\n>>>\s"])
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run the Python expression
        result = await run_shell_command(session_id, "2+3")

        # Verify output contains expected result
        assert "5" in result

    finally:
        await close_shell_session(session_id, "exit()")


@pytest.mark.asyncio
async def test_python_multiline_command():
    """Test running Python command via MCP."""
    # Start a Python session
    start_result = await start_shell_session(["python"], prompt_patterns=[r"\n>>>\s"])
    session_id = start_result.split("Session ID: ")[1]

    try:
        # should auto add a \n to the end since it's missing
        result = await run_shell_command(
            session_id,
            'for i in range(1, 6):\n    if i == 1: print("eins")\n    elif i == 2: print("zwei")\n    elif i == 3: print("drei")\n    elif i == 4: print("vier")\n    else: print("fünf")',
        )

        # Verify output contains expected result
        assert "\neins" in result
        assert "\nzwei" in result
        assert "\ndrei" in result
        assert "\nvier" in result
        assert "\nfünf" in result

    finally:
        await close_shell_session(session_id, "exit()")


@pytest.mark.asyncio
async def test_multiple_active_sessions():
    """Test managing multiple active sessions simultaneously."""
    # Start multiple sessions
    bash_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    bash_session_id = bash_result.split("Session ID: ")[1]

    tcl_result = await start_shell_session(["tclsh"], prompt_patterns=[r"%"])
    tcl_session_id = tcl_result.split("Session ID: ")[1]

    try:
        # Verify both sessions are active
        sessions_info = await get_active_sessions()
        assert bash_session_id in sessions_info
        assert tcl_session_id in sessions_info
        assert "bash" in sessions_info
        assert "tclsh" in sessions_info

        # Run commands in both sessions
        bash_result = await run_shell_command(bash_session_id, "echo 'hello world'")
        assert "hello world" in bash_result

        tcl_result = await run_shell_command(tcl_session_id, "expr 10+5")
        assert "15" in tcl_result

    finally:
        await close_shell_session(bash_session_id)
        await close_shell_session(tcl_session_id)


@pytest.mark.asyncio
async def test_close_all_sessions():
    """Test closing all sessions at once."""
    # Start multiple sessions
    session1_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session2_result = await start_shell_session(["tclsh"], prompt_patterns=[r"%"])

    # Verify sessions are active
    sessions_info = await get_active_sessions()
    assert "bash" in sessions_info
    assert "tclsh" in sessions_info

    # Close all sessions
    close_result = await close_all_sessions()
    assert "Closed 2 sessions successfully" in close_result

    # Verify no sessions remain
    sessions_info = await get_active_sessions()
    assert "No active shell sessions" in sessions_info


@pytest.mark.asyncio
async def test_dead_session_cleanup():
    """Test that dead sessions are properly cleaned up."""
    # Start a session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    # Manually kill the process to simulate a dead session
    shell = _active_sessions[session_id]
    if shell.child:
        shell.child.terminate()
        shell.child.wait()  # Wait for process to actually die

    # Try to run a command - should detect dead session and clean up
    result = await run_shell_command(session_id, "echo test")
    assert "is no longer active (process died)" in result

    # Verify session was cleaned up
    sessions_info = await get_active_sessions()
    assert "No active shell sessions" in sessions_info


@pytest.mark.asyncio
async def test_session_timeout():
    """Test command timeout handling."""
    # Start a bash session
    start_result = await start_shell_session(
        ["bash", "--norc", "-i"], prompt_patterns=[r"bash.*\$"]
    )
    session_id = start_result.split("Session ID: ")[1]

    try:
        # Run a command with very short timeout that should fail
        result = await run_shell_command(session_id, "sleep 5", timeout=0.1)

        # Should get a timeout error
        assert "Error executing command" in result

    finally:
        await close_shell_session(session_id)


@pytest.mark.asyncio
async def test_custom_exit_command():
    """Test using custom exit command for specific shells."""
    # Start a Python session
    start_result = await start_shell_session(["python"])
    session_id = start_result.split("Session ID: ")[1]

    # Close with Python-specific exit command
    close_result = await close_shell_session(session_id, "exit()")
    assert "closed successfully" in close_result
