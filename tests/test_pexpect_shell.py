import pytest
from src.pexpect_shell import PexpectInteractiveShell


def test_pexpect_interactive_shell_start_and_close():
    """Test that shell can be started and closed properly."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    shell.start()
    
    # Verify process is running
    assert shell.child is not None
    assert shell.child.isalive()
    
    # Close the shell
    shell.close()
    
    # Verify process is terminated
    assert not shell.child.isalive()


def test_pexpect_interactive_shell_start_failure():
    """Test that shell properly handles failed process start."""
    shell = PexpectInteractiveShell(["nonexistent_command_12345"], prompt_patterns=[r'bash.*\$'])
    
    with pytest.raises(RuntimeError, match="Could not start shell process"):
        shell.start()


def test_pexpect_interactive_shell_run_command():
    """Test running a simple command in the shell."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    shell.start()
    
    try:
        # Run a simple command
        result = shell.run_command("echo 'hello world'")
        
        # Verify output contains expected content
        assert "hello world" in result
        
    finally:
        shell.close()


def test_pexpect_interactive_shell_multiple_commands():
    """Test running multiple commands sequentially."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    shell.start()
    
    try:
        # Run first command
        result1 = shell.run_command("echo 'first'")
        assert "first" in result1
        
        # Run second command
        result2 = shell.run_command("echo 'second'")
        assert "second" in result2
        
    finally:
        shell.close()


def test_pexpect_interactive_shell_with_working_directory():
    """Test shell with specific working directory."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], cwd="/tmp", prompt_patterns=[r'bash.*\$'])
    shell.start()
    
    try:
        # Run a command that depends on current directory
        result = shell.run_command("pwd")
        assert "/tmp" in result
        
    finally:
        shell.close()


def test_pexpect_interactive_shell_error_handling():
    """Test error handling when shell is not started."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    
    # Try to run command without starting shell
    with pytest.raises(RuntimeError, match="Shell not started or process has exited"):
        shell.run_command("echo test")


def test_pexpect_interactive_shell_complex_command():
    """Test running a more complex command."""
    shell = PexpectInteractiveShell(["bash", "--norc", "-i"], prompt_patterns=[r'bash.*\$'])
    shell.start()
    
    try:
        # Run a command that produces multi-line output
        result = shell.run_command("ls -la")
        
        # Should contain some output
        assert len(result) > 0
        # Check that at least one line starts with 'd' and ends with '.'
        lines = result.split('\n')
        dot_line_found = any(line.startswith('d') and line.endswith('.') for line in lines if line.strip())
        assert dot_line_found
        
    finally:
        shell.close()


def test_tclsh_command():
    """Test running TCL command expr 2+3 which should result in 5."""
    shell = PexpectInteractiveShell(["tclsh"], prompt_patterns=[r'%'])
    shell.start()
    
    try:
        # Run the TCL expression
        result = shell.run_command("expr 2+3")
        
        # Verify output contains expected result
        assert "5" in result
        
    finally:
        shell.close()


def test_python_command():
    """Test running Python command 2+3 which should result in 5."""
    shell = PexpectInteractiveShell(["python", '-i'], prompt_patterns=[r'^>>> '])
    shell.start()
    
    try:
        # Run the Python expression
        result = shell.run_command("2+3")
        
        # Verify output contains expected result
        assert "5" in result
        
    finally:
        shell.close('exit()')
