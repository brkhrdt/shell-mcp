# tests/test_shell.py
import asyncio
import pytest
from shell import InteractiveShell


@pytest.mark.asyncio
async def test_interactive_shell_start_and_close():
    """Test that shell can be started and closed properly."""
    shell = InteractiveShell("bash --norc", "bash.*$")
    await shell.start()
    
    # Verify process is running
    assert shell.process is not None
    assert shell.process.poll() is None  # Process should still be running
    
    # Close the shell
    await shell.close()
    
    # Verify process is terminated
    assert shell.process.poll() is not None


@pytest.mark.asyncio
async def test_interactive_shell_run_command():
    """Test running a simple command in the shell."""
    shell = InteractiveShell("bash --norc", "bash.*$")
    await shell.start()
    
    try:
        # Run a simple command
        result = await shell.run_command("echo 'hello world'")
        
        # Verify output contains expected content
        assert "hello world" in result
        assert "$" in result  # Should contain prompt
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_interactive_shell_multiple_commands():
    """Test running multiple commands sequentially."""
    shell = InteractiveShell("bash", "$")
    await shell.start()
    
    try:
        # Run first command
        result1 = await shell.run_command("echo 'first'")
        assert "first" in result1
        
        # Run second command
        result2 = await shell.run_command("echo 'second'")
        assert "second" in result2
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_interactive_shell_with_working_directory():
    """Test shell with specific working directory."""
    shell = InteractiveShell("bash", "$", cwd="/tmp")
    await shell.start()
    
    try:
        # Run a command that depends on current directory
        result = await shell.run_command("pwd")
        assert "/tmp" in result
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_interactive_shell_error_handling():
    """Test error handling when shell is not started."""
    shell = InteractiveShell("bash", "$")
    
    # Try to run command without starting shell
    with pytest.raises(RuntimeError, match="Shell not started"):
        await shell.run_command("echo test")


@pytest.mark.asyncio
async def test_interactive_shell_complex_command():
    """Test running a more complex command."""
    shell = InteractiveShell("bash", "$")
    await shell.start()
    
    try:
        # Run a command that produces multi-line output
        result = await shell.run_command("ls -la")
        
        # Should contain prompt and some output
        assert "$" in result
        assert len(result) > 0
        
    finally:
        await shell.close()
