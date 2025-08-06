from typing import Dict, Optional, List
import uuid
import asyncio
import re
import pexpect
from mcp.server.fastmcp import FastMCP
from shell import InteractiveShell


# Initialize FastMCP server
mcp = FastMCP("interactive-shell")

# Global session storage
_active_sessions: Dict[str, InteractiveShell] = {}


@mcp.tool()
async def start_shell_session(
    shell_command: List[str],
    cwd: Optional[str] = None,
    prompt_patterns: Optional[List[str]] = None,
    timeout: float = 10,
) -> str:
    """Start a new interactive shell session.

    Args:
        shell_command: List of command and arguments to start the shell (e.g., ["bash"], ["python3"], ["tclsh"])
        cwd: Optional working directory for the shell
        prompt_patterns: Optional custom prompt patterns to recognize
        timeout: Timeout in seconds for shell operations

    Returns:
        Session ID for the started shell
    """
    session_id = str(uuid.uuid4())

    try:
        shell = InteractiveShell(
            shell_command=shell_command, cwd=cwd, prompt_patterns=prompt_patterns
        )

        # Convert to async operation
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shell.start, timeout)

        _active_sessions[session_id] = shell
        return f"Shell session started successfully. Session ID: {session_id}"

    except Exception as e:
        return f"Failed to start shell session: {str(e)}"


@mcp.tool()
async def get_active_sessions() -> str:
    """Get list of all active shell sessions.

    Returns:
        Information about active sessions
    """
    if not _active_sessions:
        return "No active shell sessions."

    session_info = []
    for session_id, shell in _active_sessions.items():
        status = "alive" if shell.child and shell.child.isalive() else "dead"
        cwd = shell.cwd or "default"
        command = " ".join(shell._shell_command_list)

        session_info.append(
            f"Session {session_id}: {command} (cwd: {cwd}, status: {status})"
        )

    return "\n".join(session_info)


@mcp.tool()
async def run_shell_command(session_id: str, command: str, timeout: float = 10) -> str:
    """Run a command in an existing shell session.

    Args:
        session_id: ID of the shell session
        command: Command to execute
        timeout: Timeout in seconds for command execution

    Returns:
        Command output
    """
    if session_id not in _active_sessions:
        return f"Session {session_id} not found. Use get_active_sessions() to see available sessions."

    shell = _active_sessions[session_id]

    if not shell.child or not shell.child.isalive():
        # Clean up dead session
        del _active_sessions[session_id]
        return f"Session {session_id} is no longer active (process died)."

    try:
        # Convert to async operation
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, shell.run_command, command, timeout)
        return output

    except Exception as e:
        return f"Error executing command in session {session_id}: {str(e)}"


@mcp.tool()
async def close_shell_session(session_id: str, exit_command: str = "exit") -> str:
    """Close a shell session.

    Args:
        session_id: ID of the shell session to close
        exit_command: Command to use for graceful exit

    Returns:
        Confirmation message
    """
    if session_id not in _active_sessions:
        return f"Session {session_id} not found."

    shell = _active_sessions[session_id]

    try:
        # Convert to async operation
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shell.close, exit_command)

        del _active_sessions[session_id]
        return f"Session {session_id} closed successfully."

    except Exception as e:
        # Still remove from active sessions even if close failed
        del _active_sessions[session_id]
        return f"Session {session_id} closed with errors: {str(e)}"


@mcp.tool()
async def close_all_sessions() -> str:
    """Close all active shell sessions.

    Returns:
        Summary of closed sessions
    """
    if not _active_sessions:
        return "No active sessions to close."

    closed_count = 0
    errors = []

    # Create a copy of session IDs to avoid modifying dict during iteration
    session_ids = list(_active_sessions.keys())

    for session_id in session_ids:
        try:
            result = await close_shell_session(session_id)
            if "successfully" in result:
                closed_count += 1
            else:
                errors.append(f"Session {session_id}: {result}")
        except Exception as e:
            errors.append(f"Session {session_id}: {str(e)}")

    summary = f"Closed {closed_count} sessions successfully."
    if errors:
        summary += f"\nErrors:\n" + "\n".join(errors)

    return summary


@mcp.tool()
async def get_shell_buffer(session_id: str) -> str:
    """Get the complete shell session buffer from command history.

    Args:
        session_id: ID of the shell session

    Returns:
        Complete session buffer reconstructed from command history
    """
    if session_id not in _active_sessions:
        return f"Session {session_id} not found. Use get_active_sessions() to see available sessions."

    shell = _active_sessions[session_id]

    if not shell.child or not shell.child.isalive():
        # Clean up dead session
        del _active_sessions[session_id]
        return f"Session {session_id} is no longer active (process died)."

        # Use read_nonblocking to get available output without affecting expect state
        buffer_content = ""
        
        # First, get any existing buffer content
        if shell.child.buffer:
            buffer_content += shell.child.buffer
        
        # Then try to read any additional available data
        try:
            # Read up to 64KB of available data without blocking
            additional_data = shell.child.read_nonblocking(size=65536, timeout=0)
            if additional_data:
                buffer_content += additional_data.decode('utf-8', errors='replace')
        except pexpect.TIMEOUT:
            # No additional data available, that's fine
            pass
        except pexpect.EOF:
            # Process has ended
            buffer_content += "\n[Process ended]"
        
        # Also include before/after if they exist (from previous expect operations)
        if hasattr(shell.child, 'before') and shell.child.before:
            before_content = shell.child.before.decode('utf-8', errors='replace')
            buffer_content = before_content + buffer_content
        
        if hasattr(shell.child, 'after') and shell.child.after:
            after_content = shell.child.after.decode('utf-8', errors='replace')
            buffer_content = buffer_content + after_content
        
        return buffer_content if buffer_content else "Buffer is empty"

    except Exception as e:
        return f"Error retrieving buffer for session {session_id}: {str(e)}"


@mcp.tool()
async def get_command_output(session_id: str) -> str:
    """Get the buffer for the last command ran in the session.

    Args:
        session_id: ID of the shell session

    Returns:
        Complete buffer for the last command executed
    """
    if session_id not in _active_sessions:
        return f"Session {session_id} not found. Use get_active_sessions() to see available sessions."

    shell = _active_sessions[session_id]

    if not shell.child or not shell.child.isalive():
        # Clean up dead session
        del _active_sessions[session_id]
        return f"Session {session_id} is no longer active (process died)."

    try:
        history = shell.get_command_history()

        if not history:
            return f"Session {session_id} has no command history."

        # Get the last command
        return history[-1].full_output

    except Exception as e:
        return f"Error retrieving buffer for session {session_id}: {str(e)}"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
