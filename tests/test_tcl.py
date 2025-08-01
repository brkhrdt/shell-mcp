import pytest
from tcl import run_tcl

@pytest.mark.asyncio
async def test_run_tcl_success():
    """Test successful Tcl command execution"""
    # Remove mocking and actually run the command
    result = await run_tcl("expr 3+2")
    assert result == "5"

@pytest.mark.asyncio
async def test_run_tcl_failure():
    """Test failed Tcl command execution"""
    result = await run_tcl("invalid_command")
    assert "Error executing Tcl command" in result
