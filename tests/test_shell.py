# tests/test_shell.py
import asyncio
import pytest
from shell import GenericInteractiveShell


@pytest.mark.asyncio
async def test_generic_interactive_shell_start_and_close():
    """Test that shell can be started and closed properly."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    await shell.start()
    
    # Verify process is running
    assert shell.process is not None
    assert shell.process.returncode is None  # Process should still be running
    
    # Close the shell
    await shell.close()
    
    # Verify process is terminated
    assert shell.process.returncode is not None


@pytest.mark.asyncio
async def test_generic_interactive_shell_run_command():
    """Test running a simple command in the shell."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    await shell.start()
    
    try:
        # Run a simple command
        result = await shell.run_command("echo 'hello world'")
        
        # Verify output contains expected content
        assert "hello world" in result
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_generic_interactive_shell_multiple_commands():
    """Test running multiple commands sequentially."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
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
async def test_generic_interactive_shell_with_working_directory():
    """Test shell with specific working directory."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], cwd="/tmp", prompt_patterns=[r'bash.*\$'])
    await shell.start()
    
    try:
        # Run a command that depends on current directory
        result = await shell.run_command("pwd")
        assert "/tmp" in result
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_generic_interactive_shell_error_handling():
    """Test error handling when shell is not started."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    
    # Try to run command without starting shell
    with pytest.raises(RuntimeError, match="Shell not started or stdin not available."):
        await shell.run_command("echo test")


@pytest.mark.asyncio
async def test_generic_interactive_shell_complex_command():
    """Test running a more complex command."""
    # Use the same command pattern as in main()
    shell = GenericInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    await shell.start()
    
    try:
        # Run a command that produces multi-line output
        result = await shell.run_command("ls -la")
        
        # Should contain some output (prompt may be stripped)
        assert len(result) > 0
        # Check that at least one line starts with 'd' and ends with '.'
        lines = result.split('\n')
        dot_line_found = any(line.startswith('d') and line.endswith('.') for line in lines if line.strip())
        assert dot_line_found
        
    finally:
        await shell.close()


@pytest.mark.asyncio
async def test_tclsh_command():
    """Test running TCL command expr 2+3 which should result in 5."""
    # Use tclsh as the shell command
    shell = GenericInteractiveShell(["tclsh"], prompt_patterns=[r'%'])
    await shell.start()
    
    try:
        # Run the TCL expression
        result = await shell.run_command("expr 2+3")
        
        # Verify output contains expected result
        assert "5" in result
        
    finally:
        await shell.close()

@pytest.mark.asyncio
async def test_python_command():
    """Test running TCL command expr 2+3 which should result in 5."""
    # Use python as the shell command
    shell = GenericInteractiveShell(["python", '-i'], prompt_patterns=[r'^>>> '])
    await shell.start()
    
    try:
        # Run the TCL expression
        result = await shell.run_command("2+3")
        
        # Verify output contains expected result
        assert "5" in result
        
    finally:
        await shell.close('exit()')
